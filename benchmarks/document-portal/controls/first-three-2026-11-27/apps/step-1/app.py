"""Evaluator-only independent Flask/SQLite control. Never release to a developer."""
import io
import json
import os
import sqlite3
import sys
import uuid
import zipfile
from flask import Flask, Response, abort, jsonify, redirect, render_template_string, request, send_file, session
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

MODE = sys.argv[1] if len(sys.argv) > 1 else 'safe'
if MODE not in {'safe', 'alternative', 'ui-only', 'reject-all', 'xss', 'archive-open', 'export-partial', 'search-leak'}:
    raise SystemExit('invalid author control')
STEP = 1
DB = os.path.join(os.environ.get('PORTAL_DATA_DIR', '/tmp'), 'portal-control.sqlite3')
app = Flask(__name__)
app.secret_key = 'disposable-control-only'


def conn():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


with conn() as db:
    db.executescript('''
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE,password TEXT);
    CREATE TABLE IF NOT EXISTS collections(id TEXT PRIMARY KEY,name TEXT,owner TEXT);
    CREATE TABLE IF NOT EXISTS members(collection_id TEXT,user_id TEXT,role TEXT,PRIMARY KEY(collection_id,user_id));
    CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,owner TEXT,collection_id TEXT,title TEXT,description TEXT,filename TEXT,kind TEXT,content TEXT,bytes BLOB,state TEXT);
    ''')


def failure(status=400):
    return jsonify(error='invalid or unavailable request'), status


def identity():
    uid = session.get('uid')
    if not uid:
        abort(401)
    return uid


def user_row(db):
    uid = identity()
    row = db.execute('SELECT id,email FROM users WHERE id=?', (uid,)).fetchone()
    if row is None:
        abort(401)
    return row


def role(db, cid, uid):
    coll = db.execute('SELECT owner FROM collections WHERE id=?', (cid,)).fetchone()
    if not coll:
        return None
    if coll['owner'] == uid:
        return 'owner'
    member = db.execute('SELECT role FROM members WHERE collection_id=? AND user_id=?', (cid,uid)).fetchone()
    return member['role'] if member else None


def permitted(db, document, uid, action):
    if MODE == 'ui-only' and action != 'write':
        return True
    if MODE == 'archive-open' and action == 'owner' and document['collection_id']:
        return True
    if document['collection_id'] is None:
        return document['owner'] == uid
    current = role(db, document['collection_id'], uid)
    if action == 'read':
        return current in {'owner', 'editor', 'reader'}
    if action == 'write':
        return current in {'owner', 'editor'}
    return current == 'owner'


def document_row(db, did, action='read'):
    row = db.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone()
    if row is None or not permitted(db, row, identity(), action):
        abort(404)
    return row


def doc_json(row, detail=False):
    result = {name: row[name] for name in ('id','title','description','filename','kind','collection_id','state')}
    if detail and row['kind'] == 'note':
        result['content'] = row['content']
    return result


@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
def http_error(error):
    if request.path.startswith('/api/'):
        return failure(error.code)
    return f'{error.code}', error.code


@app.before_request
def reject_control():
    if MODE == 'reject-all' and request.path != '/ready':
        return failure(403)


@app.get('/ready')
def ready():
    return 'ready'


@app.post('/api/users')
def create_user():
    value = request.get_json(silent=True) or {}
    email, password = value.get('email'), value.get('password')
    if not isinstance(email, str) or not isinstance(password, str) or not email or not password:
        return failure()
    uid = str(uuid.uuid4())
    try:
        with conn() as db:
            db.execute('INSERT INTO users VALUES(?,?,?)', (uid,email,generate_password_hash(password)))
    except sqlite3.IntegrityError:
        return failure(409)
    return jsonify(id=uid,email=email), 201


@app.route('/api/session', methods=['GET','POST','DELETE'])
def api_session():
    if request.method == 'DELETE':
        session.clear()
        return '', 204
    if request.method == 'GET':
        with conn() as db:
            row = user_row(db)
            return jsonify(user=dict(row))
    value = request.get_json(silent=True) or {}
    with conn() as db:
        row = db.execute('SELECT * FROM users WHERE email=?', (value.get('email'),)).fetchone()
    if row is None or not check_password_hash(row['password'], str(value.get('password'))):
        return failure(401)
    session['uid'] = row['id']
    return jsonify(user={'id':row['id'], 'email':row['email']})


def selected_documents(db, cid=None, state='active'):
    uid = identity()
    if cid:
        if not role(db, cid, uid) and MODE != 'ui-only' and not (MODE == 'archive-open' and state == 'archived'):
            abort(403)
        if state == 'archived' and role(db, cid, uid) != 'owner' and MODE not in {'ui-only','archive-open'}:
            abort(403)
        return db.execute('SELECT * FROM documents WHERE collection_id=? AND state=?', (cid,state)).fetchall()
    return db.execute('SELECT * FROM documents WHERE owner=? AND collection_id IS NULL AND state=?', (uid,state)).fetchall()


@app.route('/api/documents', methods=['GET','POST'])
def documents():
    with conn() as db:
        if request.method == 'GET':
            state = request.args.get('state', 'active')
            if state not in {'active','archived'}:
                return failure()
            return jsonify([doc_json(r) for r in selected_documents(db, request.args.get('collection_id'), state)])
        uid = identity()
        value = request.get_json(silent=True) or {}
        title, cid = value.get('title'), value.get('collection_id')
        if not isinstance(title,str) or not 0 < len(title) <= 200 or not isinstance(value.get('content'),str):
            return failure()
        if cid and role(db,cid,uid) not in {'owner','editor'}:
            return failure(403)
        did = str(uuid.uuid4())
        db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (did,uid,cid,title,value.get('description',''),'note.txt','note',value['content'],value['content'].encode(),'active'))
        return jsonify(doc_json(db.execute('SELECT * FROM documents WHERE id=?',(did,)).fetchone(), True)), 201


@app.post('/api/uploads')
def uploads():
    uid = identity()
    title, cid, file = request.form.get('title'), request.form.get('collection_id'), request.files.get('file')
    if not title or len(title) > 200 or file is None:
        return failure()
    data = file.read()
    if not 0 < len(data) <= 2 * 1024 * 1024:
        return failure()
    with conn() as db:
        if cid and role(db,cid,uid) not in {'owner','editor'}:
            return failure(403)
        did = str(uuid.uuid4())
        db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (did,uid,cid,title,request.form.get('description',''),file.filename,'file','',data,'active'))
        return jsonify(doc_json(db.execute('SELECT * FROM documents WHERE id=?',(did,)).fetchone())), 201


@app.route('/api/documents/<did>', methods=['GET','PATCH','DELETE'])
def document(did):
    with conn() as db:
        if request.method == 'GET':
            return jsonify(doc_json(document_row(db,did), True))
        if request.method == 'DELETE':
            row = document_row(db,did,'owner' if STEP >= 2 else 'write')
            if STEP >= 3:
                db.execute("UPDATE documents SET state='archived' WHERE id=?",(did,))
            else:
                db.execute('DELETE FROM documents WHERE id=?',(did,))
            return '', 204
        row = document_row(db,did,'write')
        if row['state'] == 'archived':
            return failure(403)
        value = request.get_json(silent=True) or {}
        title = value.get('title',row['title'])
        if not isinstance(title,str) or not 0 < len(title) <= 200:
            return failure()
        cid = row['collection_id']
        if 'collection_id' in value:
            if row['owner'] != identity() or (cid and role(db,cid,identity()) != 'owner'):
                return failure(403)
            cid = value['collection_id']
            if cid and role(db,cid,identity()) != 'owner':
                return failure(403)
        content = value.get('content',row['content']) if row['kind']=='note' else row['content']
        if not isinstance(content,str):
            return failure()
        db.execute('UPDATE documents SET title=?,description=?,content=?,bytes=?,collection_id=? WHERE id=?',
                   (title,value.get('description',row['description']),content,content.encode() if row['kind']=='note' else row['bytes'],cid,did))
        return jsonify(doc_json(db.execute('SELECT * FROM documents WHERE id=?',(did,)).fetchone(), True))


@app.get('/api/documents/<did>/download')
def download(did):
    with conn() as db:
        row = document_row(db,did)
        if row['state']=='archived' and row['collection_id'] and role(db,row['collection_id'],identity())!='owner' and MODE!='ui-only':
            abort(404)
        return send_file(io.BytesIO(row['bytes']),as_attachment=True,download_name=row['filename'])


@app.route('/api/collections', methods=['GET','POST'])
def collections():
    if STEP < 2:
        abort(404)
    uid = identity()
    with conn() as db:
        if request.method == 'GET':
            rows = db.execute('SELECT * FROM collections').fetchall()
            return jsonify([{'id':r['id'],'name':r['name'],'role':role(db,r['id'],uid)} for r in rows if role(db,r['id'],uid)])
        name = (request.get_json(silent=True) or {}).get('name')
        if not isinstance(name,str) or not 0 < len(name) <= 200:
            return failure()
        cid = str(uuid.uuid4())
        db.execute('INSERT INTO collections VALUES(?,?,?)',(cid,name,uid))
        return jsonify(id=cid,name=name,role='owner'), 201


@app.route('/api/collections/<cid>/members', methods=['GET','PUT'])
def members(cid):
    uid = identity()
    with conn() as db:
        if role(db,cid,uid) is None:
            abort(404)
        if request.method == 'GET':
            rows = db.execute('SELECT users.id AS user_id,users.email,members.role FROM members JOIN users ON users.id=members.user_id WHERE collection_id=?',(cid,)).fetchall()
            return jsonify([dict(r) for r in rows])
        if role(db,cid,uid)!='owner' and MODE!='ui-only':
            abort(403)
        value = request.get_json(silent=True) or {}
        if value.get('role') not in {'reader','editor'}:
            return failure()
        target = db.execute('SELECT id,email FROM users WHERE email=?',(value.get('email'),)).fetchone()
        if target is None:
            return failure(404)
        db.execute('INSERT INTO members VALUES(?,?,?) ON CONFLICT(collection_id,user_id) DO UPDATE SET role=excluded.role',(cid,target['id'],value['role']))
        return jsonify(user_id=target['id'],email=target['email'],role=value['role'])


@app.delete('/api/collections/<cid>/members/<uid>')
def remove_member(cid,uid):
    with conn() as db:
        if role(db,cid,identity())!='owner' and MODE!='ui-only':
            abort(403)
        db.execute('DELETE FROM members WHERE collection_id=? AND user_id=?',(cid,uid))
    return '',204


@app.get('/api/search')
def search():
    if STEP < 3:
        abort(404)
    query = request.args.get('q','').casefold()
    with conn() as db:
        rows = (db.execute("SELECT * FROM documents WHERE state='active'").fetchall()
                if MODE == 'search-leak' and not request.args.get('collection_id')
                else selected_documents(db,request.args.get('collection_id')))
        if MODE == 'alternative':
            # Distinct query strategy: filter in SQL rather than Python.
            ids = [r['id'] for r in rows]
            rows = db.execute('SELECT * FROM documents WHERE id IN (' + ','.join('?' for _ in ids) + ')',ids).fetchall() if ids else []
        return jsonify([doc_json(r) for r in rows if query in (r['title']+' '+r['description']+' '+(r['content'] if r['kind']=='note' else '')).casefold()])


@app.post('/api/documents/<did>/restore')
def restore(did):
    with conn() as db:
        row = document_row(db,did,'owner')
        db.execute("UPDATE documents SET state='active' WHERE id=?",(did,))
        return jsonify(doc_json(db.execute('SELECT * FROM documents WHERE id=?',(did,)).fetchone(),True))


@app.post('/api/exports')
def exports():
    ids = (request.get_json(silent=True) or {}).get('document_ids')
    if not isinstance(ids,list) or not 1 <= len(ids) <= 20 or len(set(ids)) != len(ids):
        return failure()
    with conn() as db:
        rows = [db.execute('SELECT * FROM documents WHERE id=?',(did,)).fetchone() for did in ids]
        if MODE == 'export-partial':
            rows = [r for r in rows if r is not None and r['state']=='active' and permitted(db,r,identity(),'read')]
        elif any(r is None or r['state']!='active' or not permitted(db,r,identity(),'read') for r in rows):
            return failure(403)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
            manifest = []
            for index,row in enumerate(rows):
                path = f'documents/{index}-{row["filename"]}'
                archive.writestr(path,row['bytes'])
                manifest.append({key:row[key] for key in ('id','title','description','filename')} | {'path':path})
            archive.writestr('manifest.json',json.dumps({'documents':manifest}))
        stream.seek(0)
        return send_file(stream,mimetype='application/zip',as_attachment=True,download_name='handover.zip')


BASE = '''<!doctype html><title>Fieldwork</title><nav><a href="/">My library</a> <a href="/login">Log in</a> <a href="/new/note">Write a note</a> <a href="/new/file">Upload a handout</a> <a href="/archive">Archive</a></nav>'''


@app.route('/login',methods=['GET','POST'])
def browser_login():
    if request.method == 'POST':
        with conn() as db:
            row = db.execute('SELECT * FROM users WHERE email=?',(request.form.get('email'),)).fetchone()
        if row and check_password_hash(row['password'],request.form.get('password','')):
            session['uid']=row['id']; return redirect('/')
    return '<a href="/">Home</a><form method="post"><label>Email<input name="email"></label><label>Password<input name="password" type="password"></label><button>Log in</button></form>'


@app.get('/')
def library():
    uid = session.get('uid')
    if not uid:
        return '<a href="/login">Log in</a> <a href="/register">Create account</a>'
    with conn() as db:
        rows = selected_documents(db)
        query = request.args.get('q','').casefold()
        rows = [r for r in rows if query in (r['title']+' '+r['description']+' '+r['content']).casefold()]
        colls = db.execute('SELECT * FROM collections WHERE owner=?',(uid,)).fetchall()
        return render_template_string(BASE + '''<h1>My library</h1><form method="get"><input name="q" aria-label="Search"><button>Search</button></form>
        <form method="post" action="/exports"><button>Download selected ZIP</button>
        {% for r in rows %}<label><input type="checkbox" name="document_ids" value="{{r['id']}}"> Select</label><a href="/documents/{{r['id']}}">{{r['title']}}</a>{% endfor %}</form>
        {% for c in colls %}<a href="/collections/{{c['id']}}">{{c['name']}}</a>{% endfor %}''',rows=rows,colls=colls)


@app.route('/new/note',methods=['GET','POST'])
def browser_new():
    identity()
    if request.method=='POST':
        with conn() as db:
            did=str(uuid.uuid4()); content=request.form.get('content','')
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)',(did,identity(),None,request.form['title'],'','note.txt','note',content,content.encode(),'active'))
        return redirect('/')
    return '<form method="post"><input name="title"><textarea name="content"></textarea><button>Save</button></form>'


@app.route('/new/file',methods=['GET','POST'])
def browser_upload():
    identity()
    if request.method=='POST':
        file=request.files['file']; data=file.read()
        with conn() as db:
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (str(uuid.uuid4()),identity(),None,request.form['title'],'',file.filename,'file','',data,'active'))
        return redirect('/')
    return '<form method="post" enctype="multipart/form-data"><input name="title"><input type="file" name="file"><button>Save document</button></form>'


@app.get('/documents/<did>')
def browser_detail(did):
    with conn() as db:
        row=document_row(db,did)
        return render_template_string('''<h1>{{title}}</h1><p>{{description}}</p><article>{{content}}</article>
        <a href="/documents/{{id}}/edit">Edit document</a><a href="/documents/{{id}}/download">Download</a>
        {% if state=='active' %}<form method="post" action="/documents/{{id}}/archive"><button>Archive document</button></form>
        {% else %}<form method="post" action="/documents/{{id}}/restore"><button>Restore document</button></form>{% endif %}''',
                                      **(dict(row) | ({'content':Markup(row['content']), 'description':Markup(row['description'])} if MODE=='xss' else {})))


@app.route('/documents/<did>/edit',methods=['GET','POST'])
def browser_edit(did):
    with conn() as db:
        row=document_row(db,did,'write')
        if request.method=='POST':
            title=request.form['title']; content=request.form.get('content',row['content'])
            db.execute('UPDATE documents SET title=?,content=?,bytes=? WHERE id=?',(title,content,content.encode() if row['kind']=='note' else row['bytes'],did))
            return redirect('/documents/'+did)
        return render_template_string('<form method="post"><input name="title" value="{{title}}"><textarea name="content">{{content}}</textarea><button>Save changes</button></form>',**dict(row))


@app.get('/documents/<did>/download')
def browser_download(did):
    with conn() as db:
        row=document_row(db,did)
        return send_file(io.BytesIO(row['bytes']),as_attachment=True,download_name=row['filename'])


@app.post('/documents/<did>/archive')
def browser_archive_document(did):
    with conn() as db:
        document_row(db,did,'owner')
        db.execute("UPDATE documents SET state='archived' WHERE id=?",(did,))
    return redirect('/archive')


@app.post('/documents/<did>/restore')
def browser_restore_document(did):
    with conn() as db:
        document_row(db,did,'owner')
        db.execute("UPDATE documents SET state='active' WHERE id=?",(did,))
    return redirect('/documents/'+did)


@app.post('/exports')
def browser_export():
    with conn() as db:
        ids=request.form.getlist('document_ids')
        rows=[document_row(db,did) for did in ids]
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
            manifest=[]
            for index,row in enumerate(rows):
                path=f'documents/{index}-{row["filename"]}'
                archive.writestr(path,row['bytes'])
                manifest.append({key:row[key] for key in ('id','title','description','filename')} | {'path':path})
            archive.writestr('manifest.json',json.dumps({'documents':manifest}))
        stream.seek(0)
        return send_file(stream,mimetype='application/zip',as_attachment=True,download_name='handover.zip')


@app.get('/collections/<cid>')
def browser_collection(cid):
    with conn() as db:
        rows=selected_documents(db,cid)
        return render_template_string('''<h1>Engagement A</h1><p>Members and collaborators</p>
        {% for r in rows %}<p>{{r["title"]}}</p>{% endfor %}
        <form method="post"><input name="email" aria-label="Email"><select name="role"><option value="reader">Reader</option><option value="editor">Editor</option></select><button>Save member</button></form>''',rows=rows)


@app.post('/collections/<cid>')
def browser_add_member(cid):
    with conn() as db:
        if role(db,cid,identity())!='owner':
            abort(403)
        row=db.execute('SELECT id FROM users WHERE email=?',(request.form.get('email'),)).fetchone()
        if row is None:
            abort(404)
        db.execute('INSERT INTO members VALUES(?,?,?) ON CONFLICT(collection_id,user_id) DO UPDATE SET role=excluded.role',
                   (cid,row['id'],request.form['role']))
    return redirect('/collections/'+cid)


@app.get('/archive')
def browser_archive():
    with conn() as db:
        rows=selected_documents(db,state='archived')
        return render_template_string(BASE+'<h1>Archive</h1>{% for r in rows %}<a href="/documents/{{r["id"]}}">{{r["title"]}}</a>{% endfor %}',rows=rows)


if __name__=='__main__':
    app.run(host='0.0.0.0',port=8123)

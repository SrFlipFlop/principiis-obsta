"""Evaluator-only independent Flask/SQLite control for Document Portal steps 1-10. Never release to a developer."""
import base64
import datetime
import hashlib
import hmac
import http.client
import io
import ipaddress
import json
import os
import posixpath
import secrets
import socket
import sqlite3
import sys
import threading
import time
import urllib.parse
import uuid
import zipfile
from flask import Flask, abort, jsonify, redirect, render_template_string, request, send_file, session
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

CONTROLS = {'safe', 'alternative', 'ui-only', 'reject-all'}
# Author-only fixture variants: each breaks exactly one hidden security property.
VARIANTS = {'ssrf-open', 'ssrf-redirect', 'import-no-limit', 'retry-stale-role', 'share-survives-archive',
            'share-member-manage', 'share-xss', 'history-open', 'revision-restore-editor', 'cursor-scope-leak',
            'transfer-open', 'owner-demotable', 'transfer-keeps-links'}
MODE = sys.argv[1] if len(sys.argv) > 1 else 'safe'
if MODE not in CONTROLS | VARIANTS:
    raise SystemExit('invalid author control')
STEP = 10
DB = os.path.join(os.environ.get('PORTAL_DATA_DIR', '/tmp'), 'portal-control.sqlite3')
FIXTURE_ORIGIN = os.environ.get('PORTAL_IMPORT_FIXTURE_ORIGIN', 'http://127.0.0.1:8124').rstrip('/')
MAX_BYTES = 2 * 1024 * 1024
ALT = MODE == 'alternative'
UI_ONLY = MODE == 'ui-only'
app = Flask(__name__)
app.secret_key = 'disposable-control-only'
CURSOR_KEY = b'disposable-cursor-key'


def conn():
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


with conn() as db:
    db.executescript('''
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE,password TEXT);
    CREATE TABLE IF NOT EXISTS collections(id TEXT PRIMARY KEY,name TEXT,owner TEXT);
    CREATE TABLE IF NOT EXISTS members(collection_id TEXT,user_id TEXT,role TEXT,PRIMARY KEY(collection_id,user_id));
    CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,owner TEXT,collection_id TEXT,title TEXT,description TEXT,filename TEXT,kind TEXT,content TEXT,bytes BLOB,state TEXT);
    CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY,user_id TEXT,collection_id TEXT,url TEXT,title TEXT,description TEXT,status TEXT,document_id TEXT,error TEXT);
    CREATE TABLE IF NOT EXISTS shares(id TEXT PRIMARY KEY,document_id TEXT,token TEXT UNIQUE,expires_at REAL,revoked INTEGER DEFAULT 0,cancelled INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS revisions(document_id TEXT,number INTEGER,created_by TEXT,title TEXT,description TEXT,filename TEXT,kind TEXT,content TEXT,bytes BLOB,PRIMARY KEY(document_id,number));
    CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY,value INTEGER);
    ''')
    # Interrupted jobs become failed and retryable after a restart.
    db.execute("UPDATE imports SET status='failed',error='interrupted by restart' WHERE status='pending'")


def new_id(db):
    if not ALT:
        return str(uuid.uuid4())
    # Alternative: sequential decimal strings, so string order differs from numeric order.
    db.execute("INSERT INTO counters VALUES('id',7) ON CONFLICT(name) DO UPDATE SET value=value+1")
    return str(db.execute("SELECT value FROM counters WHERE name='id'").fetchone()[0])


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
    member = db.execute('SELECT role FROM members WHERE collection_id=? AND user_id=?', (cid, uid)).fetchone()
    return member['role'] if member else None


def permitted(db, document, uid, action):
    """action: read | write | owner."""
    if UI_ONLY and action != 'write':
        return True
    if document['collection_id'] is None:
        allowed = document['owner'] == uid
        return allowed
    current = role(db, document['collection_id'], uid)
    if action == 'read':
        if document['state'] == 'archived':
            return current == 'owner'
        return current in {'owner', 'editor', 'reader'}
    if action == 'write':
        return current in {'owner', 'editor'}
    return current == 'owner'


def can_upload(db, uid, cid):
    if UI_ONLY:
        return True
    return True if not cid else role(db, cid, uid) in {'owner', 'editor'}


def document_row(db, did, action='read'):
    row = db.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone()
    if row is None or not permitted(db, row, identity(), action):
        abort(404)
    return row


def doc_json(row, detail=False):
    result = {name: row[name] for name in ('id', 'title', 'description', 'filename', 'kind', 'collection_id')}
    if STEP >= 3:
        result['state'] = row['state']
    if detail and row['kind'] == 'note':
        result['content'] = row['content']
    return result


def add_revision(db, did, uid):
    row = db.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone()
    number = db.execute('SELECT COALESCE(MAX(number),0)+1 FROM revisions WHERE document_id=?', (did,)).fetchone()[0]
    db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?,?,?,?)',
               (did, number, uid, row['title'], row['description'], row['filename'], row['kind'], row['content'], row['bytes']))


def create_document(db, uid, cid, title, description, filename, kind, content, data):
    did = new_id(db)
    db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)',
               (did, uid, cid, title, description, filename, kind, content, data, 'active'))
    add_revision(db, did, uid)
    return did


def cancel_shares(db, did):
    db.execute('UPDATE shares SET cancelled=1 WHERE document_id=?', (did,))


def set_state(db, did, state):
    db.execute('UPDATE documents SET state=? WHERE id=?', (state, did))
    if state == 'archived' and MODE != 'share-survives-archive':
        cancel_shares(db, did)


def apply_patch(db, row, uid, value):
    """Shared by the API and browser forms. Returns an error response or None."""
    if row['state'] == 'archived':
        return failure(403)
    title = value.get('title', row['title'])
    description = value.get('description', row['description'])
    if not isinstance(title, str) or not 0 < len(title) <= 200 or not isinstance(description, str):
        return failure()
    cid = row['collection_id']
    if 'collection_id' in value:
        if not UI_ONLY and (row['owner'] != uid or (cid and role(db, cid, uid) != 'owner')):
            return failure(403)
        cid = value['collection_id']
        if cid and role(db, cid, uid) != 'owner' and not UI_ONLY:
            return failure(403)
    content = value.get('content', row['content']) if row['kind'] == 'note' else row['content']
    if not isinstance(content, str):
        return failure()
    changed = (title, description, content) != (row['title'], row['description'], row['content'])
    moved = cid != row['collection_id']
    db.execute('UPDATE documents SET title=?,description=?,content=?,bytes=?,collection_id=? WHERE id=?',
               (title, description, content, content.encode() if row['kind'] == 'note' else row['bytes'], cid, row['id']))
    if changed:
        add_revision(db, row['id'], uid)
    if moved and MODE != 'share-survives-archive':
        cancel_shares(db, row['id'])
    return None


@app.errorhandler(400)
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
            db.execute('INSERT INTO users VALUES(?,?,?)', (uid, email, generate_password_hash(password)))
    except sqlite3.IntegrityError:
        return failure(409)
    return jsonify(id=uid, email=email), 201


@app.route('/api/session', methods=['GET', 'POST', 'DELETE'])
def api_session():
    if request.method == 'DELETE':
        session.clear()
        return '', 204
    if request.method == 'GET':
        with conn() as db:
            return jsonify(user=dict(user_row(db)))
    value = request.get_json(silent=True) or {}
    with conn() as db:
        row = db.execute('SELECT * FROM users WHERE email=?', (value.get('email'),)).fetchone()
    if row is None or not check_password_hash(row['password'], str(value.get('password'))):
        return failure(401)
    session['uid'] = row['id']
    return jsonify(user={'id': row['id'], 'email': row['email']})


def selected_documents(db, cid=None, state='active'):
    uid = identity()
    if cid:
        current = role(db, cid, uid)
        if not current and not UI_ONLY:
            abort(403)
        if state == 'archived' and current != 'owner' and not UI_ONLY:
            abort(403)
        return db.execute('SELECT * FROM documents WHERE collection_id=? AND state=?', (cid, state)).fetchall()
    return db.execute('SELECT * FROM documents WHERE owner=? AND collection_id IS NULL AND state=?', (uid, state)).fetchall()


def text_of(row):
    return row['title'] + ' ' + row['description'] + ' ' + (row['content'] if row['kind'] == 'note' else '')


class Invalid(Exception):
    pass


def listing(db, endpoint, args):
    """Documents/search listing with the step-9 filters and opt-in pagination."""
    state = 'active' if endpoint == 'search' else args.get('state', 'active')
    if state not in {'active', 'archived'}:
        raise Invalid()
    kind = title_prefix = page_size = None
    if STEP >= 9:
        kind, title_prefix = args.get('kind'), args.get('title_prefix')
        if kind is not None and kind not in {'note', 'file'}:
            raise Invalid()
        if 'page_size' in args:
            raw = args['page_size']
            if not raw.isdigit() or not 1 <= int(raw) <= 100:
                raise Invalid()
            page_size = int(raw)
    cid = args.get('collection_id')
    fingerprint = json.dumps([endpoint, args.get('q', '') if endpoint == 'search' else None, cid, state, kind,
                              title_prefix, page_size])
    after = scope_owner = None
    if page_size is not None and 'cursor' in args:
        after, scope_owner = decode_cursor(args['cursor'], fingerprint)
    if MODE == 'cursor-scope-leak' and scope_owner and not cid:
        # Variant bug: trusts the library owner recorded in a client-supplied cursor.
        rows = db.execute('SELECT * FROM documents WHERE owner=? AND collection_id IS NULL AND state=?', (scope_owner, state)).fetchall()
    else:
        rows = selected_documents(db, cid, state)
    if endpoint == 'search':
        query = args.get('q', '').casefold()
        rows = [r for r in rows if query in text_of(r).casefold()]
    if kind:
        rows = [r for r in rows if r['kind'] == kind]
    if title_prefix:
        rows = [r for r in rows if r['title'].casefold().startswith(title_prefix.casefold())]
    if page_size is None:
        if 'cursor' in args and STEP >= 9:
            raise Invalid()
        return [doc_json(r) for r in rows]
    rows = sorted(rows, key=lambda r: r['id'])
    if after is not None:
        rows = [r for r in rows if r['id'] > after]
    page = rows[:page_size]
    owner = (scope_owner or identity()) if MODE == 'cursor-scope-leak' and not cid else None
    next_cursor = encode_cursor(page[-1]['id'], fingerprint, owner) if len(rows) > page_size else None
    return {'items': [doc_json(r) for r in page], 'next_cursor': next_cursor}


def encode_cursor(after, fingerprint, owner=None):
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()
    if owner:
        return base64.urlsafe_b64encode(json.dumps({'after': after, 'f': digest, 'owner': owner}).encode()).decode()
    if ALT:
        payload = f'{after}|{digest}'
        mac = hmac.new(CURSOR_KEY, payload.encode(), 'sha256').hexdigest()[:16]
        return payload.encode().hex() + '.' + mac
    return base64.urlsafe_b64encode(json.dumps({'after': after, 'f': digest}).encode()).decode()


def decode_cursor(cursor, fingerprint):
    digest = hashlib.sha256(fingerprint.encode()).hexdigest()
    try:
        if ALT:
            hexed, mac = cursor.split('.')
            payload = bytes.fromhex(hexed).decode()
            if not hmac.compare_digest(mac, hmac.new(CURSOR_KEY, payload.encode(), 'sha256').hexdigest()[:16]):
                raise ValueError
            after, seen = payload.split('|')
        else:
            value = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            after, seen = value['after'], value['f']
            owner = value.get('owner') if MODE == 'cursor-scope-leak' else None
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, AttributeError):
        raise Invalid()
    if seen != digest or not isinstance(after, str):
        raise Invalid()
    return after, (owner if not ALT else None)


@app.route('/api/documents', methods=['GET', 'POST'])
def documents():
    with conn() as db:
        if request.method == 'GET':
            try:
                return jsonify(listing(db, 'documents', request.args))
            except Invalid:
                return failure()
        uid = identity()
        value = request.get_json(silent=True) or {}
        title, cid = value.get('title'), value.get('collection_id')
        if not isinstance(title, str) or not 0 < len(title) <= 200 or not isinstance(value.get('content'), str):
            return failure()
        description = value.get('description', '')
        if not isinstance(description, str):
            return failure()
        if cid and role(db, cid, uid) not in {'owner', 'editor'}:
            return failure(403)
        did = create_document(db, uid, cid, title, description, 'note.txt', 'note', value['content'], value['content'].encode())
        return jsonify(doc_json(db.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone(), True)), 201


@app.post('/api/uploads')
def uploads():
    uid = identity()
    title, cid, file = request.form.get('title'), request.form.get('collection_id'), request.files.get('file')
    if not title or len(title) > 200 or file is None:
        return failure()
    data = file.read()
    if not 0 < len(data) <= MAX_BYTES:
        return failure()
    with conn() as db:
        if cid and role(db, cid, uid) not in {'owner', 'editor'}:
            return failure(403)
        did = create_document(db, uid, cid, title, request.form.get('description', ''), file.filename, 'file', '', data)
        return jsonify(doc_json(db.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone())), 201


@app.route('/api/documents/<did>', methods=['GET', 'PATCH', 'DELETE'])
def document(did):
    with conn() as db:
        if request.method == 'GET':
            return jsonify(doc_json(document_row(db, did), True))
        if request.method == 'DELETE':
            document_row(db, did, 'owner' if STEP >= 2 else 'write')
            if STEP >= 3:
                set_state(db, did, 'archived')
            else:
                db.execute('DELETE FROM documents WHERE id=?', (did,))
            return '', 204
        row = document_row(db, did, 'write')
        error = apply_patch(db, row, identity(), request.get_json(silent=True) or {})
        if error:
            return error
        return jsonify(doc_json(db.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone(), True))


@app.get('/api/documents/<did>/download')
def download(did):
    with conn() as db:
        row = document_row(db, did)
        return send_file(io.BytesIO(row['bytes']), as_attachment=True, download_name=row['filename'])


@app.route('/api/collections', methods=['GET', 'POST'])
def collections():
    if STEP < 2:
        abort(404)
    uid = identity()
    with conn() as db:
        if request.method == 'GET':
            rows = db.execute('SELECT * FROM collections').fetchall()
            return jsonify([{'id': r['id'], 'name': r['name'], 'role': role(db, r['id'], uid)} for r in rows if role(db, r['id'], uid)])
        name = (request.get_json(silent=True) or {}).get('name')
        if not isinstance(name, str) or not 0 < len(name) <= 200:
            return failure()
        cid = new_id(db)
        db.execute('INSERT INTO collections VALUES(?,?,?)', (cid, name, uid))
        return jsonify(id=cid, name=name, role='owner'), 201


def put_member(db, cid, email, new_role):
    """Returns (status, body). Ordinary membership changes never touch the owner."""
    if new_role not in {'reader', 'editor'}:
        return 400, None
    target = db.execute('SELECT id,email FROM users WHERE email=?', (email,)).fetchone()
    if target is None:
        return 404, None
    owner = db.execute('SELECT owner FROM collections WHERE id=?', (cid,)).fetchone()['owner']
    if target['id'] == owner:
        if MODE != 'owner-demotable' or STEP < 10:
            return 400, None
        db.execute('UPDATE collections SET owner=NULL WHERE id=?', (cid,))
    db.execute('INSERT INTO members VALUES(?,?,?) ON CONFLICT(collection_id,user_id) DO UPDATE SET role=excluded.role',
               (cid, target['id'], new_role))
    return 200, {'user_id': target['id'], 'email': target['email'], 'role': new_role}


@app.route('/api/collections/<cid>/members', methods=['GET', 'PUT'])
def members(cid):
    uid = identity()
    with conn() as db:
        if role(db, cid, uid) is None:
            abort(404)
        if request.method == 'GET':
            rows = db.execute('SELECT users.id AS user_id,users.email,members.role FROM members JOIN users ON users.id=members.user_id WHERE collection_id=?', (cid,)).fetchall()
            return jsonify([dict(r) for r in rows])
        if role(db, cid, uid) != 'owner' and not UI_ONLY:
            abort(403)
        value = request.get_json(silent=True) or {}
        status, body = put_member(db, cid, value.get('email'), value.get('role'))
        return (jsonify(body), 200) if body else failure(status)


@app.delete('/api/collections/<cid>/members/<uid>')
def remove_member(cid, uid):
    with conn() as db:
        if role(db, cid, identity()) != 'owner' and not UI_ONLY:
            abort(403)
        owner = db.execute('SELECT owner FROM collections WHERE id=?', (cid,)).fetchone()
        if owner and owner['owner'] == uid:
            if MODE != 'owner-demotable' or STEP < 10:
                return failure(400)
            db.execute('UPDATE collections SET owner=NULL WHERE id=?', (cid,))
        db.execute('DELETE FROM members WHERE collection_id=? AND user_id=?', (cid, uid))
    return '', 204


def do_transfer(db, cid, uid, email, retain):
    """Returns (status, body). Supersedes request 2's fixed-owner rule from step 10."""
    coll = db.execute('SELECT * FROM collections WHERE id=?', (cid,)).fetchone()
    current = role(db, cid, uid) if coll else None
    if current is None:
        return 404, None
    if current != 'owner' and not (MODE == 'transfer-open' or UI_ONLY):
        return 403, None
    if not isinstance(retain, bool) or not isinstance(email, str):
        return 400, None
    target = db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
    former = coll['owner']
    if target is None:
        return 404, None
    if target['id'] == former:
        return 400, None
    db.execute('DELETE FROM members WHERE collection_id=? AND user_id IN (?,?)', (cid, target['id'], former))
    db.execute('UPDATE collections SET owner=? WHERE id=?', (target['id'], cid))
    if retain:
        db.execute('INSERT INTO members VALUES(?,?,?)', (cid, former, 'editor'))
    if MODE != 'transfer-keeps-links':
        for row in db.execute('SELECT id FROM documents WHERE collection_id=?', (cid,)).fetchall():
            cancel_shares(db, row['id'])
    return 200, {'id': cid, 'name': coll['name'], 'role': 'editor' if retain else None, 'owner_id': target['id']}


@app.post('/api/collections/<cid>/transfer')
def transfer(cid):
    if STEP < 10:
        abort(404)
    uid = identity()
    value = request.get_json(silent=True) or {}
    with conn() as db:
        status, body = do_transfer(db, cid, uid, value.get('email'), value.get('retain_former_owner'))
    return (jsonify(body), 200) if body else failure(status)


@app.get('/api/search')
def search():
    if STEP < 3:
        abort(404)
    with conn() as db:
        try:
            return jsonify(listing(db, 'search', request.args))
        except Invalid:
            return failure()


@app.post('/api/documents/<did>/restore')
def restore(did):
    with conn() as db:
        document_row(db, did, 'owner')
        set_state(db, did, 'active')
        return jsonify(doc_json(db.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone(), True))


def export_rows(db, ids):
    limit = 100 if STEP >= 9 else 20
    if not isinstance(ids, list) or not 1 <= len(ids) <= limit or len(set(map(str, ids))) != len(ids):
        return None
    rows = [db.execute('SELECT * FROM documents WHERE id=?', (str(did),)).fetchone() for did in ids]
    if any(r is None or r['state'] != 'active' or not permitted(db, r, identity(), 'read') for r in rows):
        return None
    return rows


def zip_response(rows):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_STORED if ALT else zipfile.ZIP_DEFLATED) as archive:
        manifest = []
        for index, row in enumerate(rows):
            path = f'files/{row["id"]}/{row["filename"]}' if ALT else f'documents/{index}-{row["filename"]}'
            archive.writestr(path, row['bytes'])
            manifest.append({key: row[key] for key in ('id', 'title', 'description', 'filename')} | {'path': path})
        archive.writestr('manifest.json', json.dumps({'documents': manifest}))
    stream.seek(0)
    return send_file(stream, mimetype='application/zip', as_attachment=True, download_name='handover.zip')


@app.post('/api/exports')
def exports():
    with conn() as db:
        rows = export_rows(db, (request.get_json(silent=True) or {}).get('document_ids'))
        return failure(403) if rows is None else zip_response(rows)


# ---- Step 4: URL imports -------------------------------------------------

def job_json(row):
    return {'id': row['id'], 'status': row['status'], 'document_id': row['document_id'], 'error': row['error']}


def destination_allowed(url):
    parts = urllib.parse.urlsplit(url)
    origin = f'{parts.scheme}://{parts.netloc}'.lower()
    if origin == FIXTURE_ORIGIN.lower():
        return True
    if MODE == 'ssrf-open':
        return True
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80))
    except (OSError, UnicodeError):
        return False
    return bool(infos) and all(ipaddress.ip_address(info[4][0].split('%')[0]).is_global for info in infos)


def fetch(url):
    """Returns (final_url, bytes); raises ValueError with a useful message."""
    deadline = None if MODE == 'import-no-limit' else time.monotonic() + 5
    limit = None if MODE == 'import-no-limit' else MAX_BYTES
    for hop in range(6):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in {'http', 'https'} or not parts.hostname:
            raise ValueError('only http and https URLs can be imported')
        if (hop == 0 or MODE != 'ssrf-redirect') and not destination_allowed(url):
            raise ValueError('destination is not allowed')
        remaining = None if deadline is None else deadline - time.monotonic()
        if remaining is not None and remaining <= 0:
            raise ValueError('timed out')
        factory = http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection
        connection = factory(parts.hostname, parts.port, timeout=remaining)
        try:
            connection.request('GET', (parts.path or '/') + ('?' + parts.query if parts.query else ''))
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308} and response.getheader('Location'):
                url = urllib.parse.urljoin(url, response.getheader('Location'))
                continue
            if not 200 <= response.status < 300:
                raise ValueError(f'download failed with HTTP status {response.status}')
            chunks, size = [], 0
            while True:
                # The socket timeout bounds each blocking call by the time left at
                # connection; this check bounds a slow trickle of bytes.
                if deadline is not None and deadline - time.monotonic() <= 0:
                    raise ValueError('timed out')
                chunk = response.read1(65536)
                if not chunk:
                    break
                size += len(chunk)
                if limit is not None and size > limit:
                    raise ValueError('file is larger than 2 MiB')
                chunks.append(chunk)
            if size == 0:
                raise ValueError('empty download')
            return url, b''.join(chunks)
        except (OSError, http.client.HTTPException) as error:
            raise ValueError(f'download failed: {type(error).__name__}')
        finally:
            connection.close()
    raise ValueError('too many redirects')


def run_job(jid):
    with conn() as db:
        job = db.execute('SELECT * FROM imports WHERE id=?', (jid,)).fetchone()
    try:
        final, data = fetch(job['url'])
    except ValueError as error:
        with conn() as db:
            db.execute("UPDATE imports SET status='failed',error=? WHERE id=?", (str(error) or 'import failed', jid))
        return
    with conn() as db:
        if MODE != 'retry-stale-role' and not can_upload(db, job['user_id'], job['collection_id']):
            db.execute("UPDATE imports SET status='failed',error='you can no longer upload to this location' WHERE id=?", (jid,))
            return
        name = posixpath.basename(urllib.parse.unquote(urllib.parse.urlsplit(final).path)) or 'handout.bin'
        did = create_document(db, job['user_id'], job['collection_id'], job['title'], job['description'], name, 'file', '', data)
        db.execute("UPDATE imports SET status='complete',document_id=?,error=NULL WHERE id=?", (did, jid))


def start_job(jid):
    if ALT:
        run_job(jid)  # Alternative: completes or fails within the request.
    else:
        threading.Thread(target=run_job, args=(jid,), daemon=True).start()


def create_import(db, uid, value):
    url, title, description = value.get('url'), value.get('title'), value.get('description', '')
    cid = value.get('collection_id') or None
    if not isinstance(url, str) or urllib.parse.urlsplit(url).scheme not in {'http', 'https'} or not urllib.parse.urlsplit(url).hostname:
        return None, 400
    if not isinstance(title, str) or not 0 < len(title) <= 200 or not isinstance(description, str):
        return None, 400
    if cid and role(db, cid, uid) is None and not UI_ONLY:
        return None, 404
    if not can_upload(db, uid, cid):
        return None, 403
    jid = new_id(db)
    db.execute('INSERT INTO imports VALUES(?,?,?,?,?,?,?,?,?)', (jid, uid, cid, url, title, description, 'pending', None, None))
    return jid, 202


def owned_job(db, jid):
    row = db.execute('SELECT * FROM imports WHERE id=?', (jid,)).fetchone()
    if row is None or (row['user_id'] != identity() and not UI_ONLY):
        abort(404)
    return row


def retry_job(db, row):
    if row['status'] != 'failed':
        return 409
    if MODE != 'retry-stale-role' and not can_upload(db, row['user_id'], row['collection_id']):
        return 403
    db.execute("UPDATE imports SET status='pending',error=NULL WHERE id=?", (row['id'],))
    return 202


@app.post('/api/imports')
def api_import():
    if STEP < 4:
        abort(404)
    uid = identity()
    with conn() as db:
        jid, status = create_import(db, uid, request.get_json(silent=True) or {})
    if jid is None:
        return failure(status)
    start_job(jid)
    with conn() as db:
        return jsonify(job_json(owned_job(db, jid))), 202


@app.get('/api/imports/<jid>')
def api_job(jid):
    if STEP < 4:
        abort(404)
    with conn() as db:
        return jsonify(job_json(owned_job(db, jid)))


@app.post('/api/imports/<jid>/retry')
def api_retry(jid):
    if STEP < 4:
        abort(404)
    with conn() as db:
        status = retry_job(db, owned_job(db, jid))
    if status != 202:
        return failure(status)
    start_job(jid)
    with conn() as db:
        return jsonify(job_json(owned_job(db, jid))), 202


# ---- Step 5: client links -------------------------------------------------

def rfc3339(epoch):
    return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def share_json(row, detail=False):
    result = {'id': row['id'], 'url': request.host_url + 'share/' + row['token'], 'expires_at': rfc3339(row['expires_at'])}
    if detail:
        result['revoked'] = bool(row['revoked'] or row['cancelled'])
    return result


def share_manager(db, did):
    row = db.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone()
    action = 'read' if MODE == 'share-member-manage' else 'owner'
    if row is None or not permitted(db, row, identity(), action):
        abort(404)
    return row


def create_share(db, row, lifetime):
    if row['state'] != 'active':
        return None, 409
    if isinstance(lifetime, bool) or not isinstance(lifetime, int) or not 1 <= lifetime <= 86400:
        return None, 400
    sid = new_id(db)
    token = secrets.token_hex(24) if ALT else secrets.token_urlsafe(24)
    db.execute('INSERT INTO shares(id,document_id,token,expires_at) VALUES(?,?,?,?)', (sid, row['id'], token, time.time() + lifetime))
    return db.execute('SELECT * FROM shares WHERE id=?', (sid,)).fetchone(), 201


@app.route('/api/documents/<did>/shares', methods=['GET', 'POST'])
def api_shares(did):
    if STEP < 5:
        abort(404)
    with conn() as db:
        row = share_manager(db, did)
        if request.method == 'GET':
            return jsonify([share_json(s, True) for s in db.execute('SELECT * FROM shares WHERE document_id=? ORDER BY expires_at', (did,))])
        share, status = create_share(db, row, (request.get_json(silent=True) or {}).get('expires_in_seconds'))
        return (jsonify(share_json(share)), 201) if share else failure(status)


@app.delete('/api/shares/<sid>')
def api_revoke(sid):
    if STEP < 5:
        abort(404)
    with conn() as db:
        share = db.execute('SELECT * FROM shares WHERE id=?', (sid,)).fetchone()
        if share is None:
            abort(404)
        share_manager(db, share['document_id'])
        db.execute('UPDATE shares SET revoked=1 WHERE id=?', (sid,))
    return '', 204


def shared_document(db, token):
    share = db.execute('SELECT * FROM shares WHERE token=?', (token,)).fetchone()
    if share is None or share['revoked'] or share['cancelled'] or share['expires_at'] <= time.time():
        abort(404 if share is None else 410)
    row = db.execute('SELECT * FROM documents WHERE id=?', (share['document_id'],)).fetchone()
    if row is None or (row['state'] != 'active' and MODE != 'share-survives-archive'):
        abort(410)
    return row


@app.get('/share/<token>')
def share_page(token):
    if STEP < 5:
        abort(404)
    with conn() as db:
        row = shared_document(db, token)
    values = dict(row)
    if MODE == 'share-xss':
        values |= {'description': Markup(row['description']), 'content': Markup(row['content'])}
    return render_template_string('''<!doctype html><title>Client handout</title><h1>{{title}}</h1><p>{{description}}</p>
    {% if kind == 'note' %}<pre>{{content}}</pre>{% endif %}<a href="/share/{{token}}/download">Download handout</a>''', token=token, **values)


@app.get('/share/<token>/download')
def share_download(token):
    if STEP < 5:
        abort(404)
    with conn() as db:
        row = shared_document(db, token)
    return send_file(io.BytesIO(row['bytes']), as_attachment=True, download_name=row['filename'])


# ---- Step 7: revision history ----------------------------------------------

def history_document(db, did):
    row = db.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone()
    if row is None:
        abort(404)
    if MODE == 'history-open':
        identity()
        return row
    if not permitted(db, row, identity(), 'read'):
        abort(404)
    return row


def revision_json(row, detail=False):
    result = {'number': row['number'], 'created_by': row['created_by'], 'title': row['title'], 'description': row['description'],
              'filename': row['filename'], 'kind': row['kind']}
    if detail and row['kind'] == 'note':
        result['content'] = row['content']
    return result


def revision_row(db, did, number):
    history_document(db, did)
    row = db.execute('SELECT * FROM revisions WHERE document_id=? AND number=?', (did, number)).fetchone()
    if row is None:
        abort(404)
    return row


def restore_revision(db, did, number):
    row = db.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone()
    action = 'write' if MODE == 'revision-restore-editor' else 'owner'
    if row is None or not permitted(db, row, identity(), action):
        return 404
    if row['state'] != 'active':
        return 409
    revision = db.execute('SELECT * FROM revisions WHERE document_id=? AND number=?', (did, number)).fetchone()
    if revision is None:
        return 404
    db.execute('UPDATE documents SET title=?,description=?,filename=?,content=?,bytes=? WHERE id=?',
               (revision['title'], revision['description'], revision['filename'], revision['content'], revision['bytes'], did))
    add_revision(db, did, identity())
    return 200


@app.get('/api/documents/<did>/revisions')
def api_revisions(did):
    if STEP < 7:
        abort(404)
    with conn() as db:
        history_document(db, did)
        return jsonify([revision_json(r) for r in db.execute('SELECT * FROM revisions WHERE document_id=? ORDER BY number', (did,))])


@app.get('/api/documents/<did>/revisions/<int:number>')
def api_revision(did, number):
    if STEP < 7:
        abort(404)
    with conn() as db:
        return jsonify(revision_json(revision_row(db, did, number), True))


@app.get('/api/documents/<did>/revisions/<int:number>/download')
def api_revision_download(did, number):
    if STEP < 7:
        abort(404)
    with conn() as db:
        row = revision_row(db, did, number)
    return send_file(io.BytesIO(row['bytes']), as_attachment=True, download_name=row['filename'])


@app.post('/api/documents/<did>/revisions/<int:number>/restore')
def api_revision_restore(did, number):
    if STEP < 7:
        abort(404)
    with conn() as db:
        status = restore_revision(db, did, number)
        if status != 200:
            return failure(status)
        return jsonify(doc_json(db.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone(), True))


# ---- Browser pages ----------------------------------------------------------

def nav():
    links = ['<a href="/">My library</a>', '<a href="/login">Log in</a>', '<a href="/new/note">Write a note</a>',
             '<a href="/new/file">Upload a handout</a>']
    if STEP >= 4:
        links.append('<a href="/imports/new">Import from URL</a>')
    links.append('<a href="/archive">Archive</a>')
    return '<!doctype html><title>Fieldwork</title><nav>' + ' '.join(links) + '</nav>'


@app.route('/login', methods=['GET', 'POST'])
def browser_login():
    if request.method == 'POST':
        with conn() as db:
            row = db.execute('SELECT * FROM users WHERE email=?', (request.form.get('email'),)).fetchone()
        if row and check_password_hash(row['password'], request.form.get('password', '')):
            session['uid'] = row['id']
            return redirect('/')
    return '<a href="/">Home</a><form method="post"><label>Email<input name="email"></label><label>Password<input name="password" type="password"></label><button>Log in</button></form>'


LIBRARY = '''<h1>{{heading}}</h1><form method="get"><input name="q" aria-label="Search" value="{{q}}">
{% if step >= 9 %}<label>Kind<select name="kind"><option value="">All</option><option value="note">Notes</option><option value="file">Files</option></select></label>
<label>Title prefix<input name="title_prefix" value="{{prefix}}"></label>{% endif %}<button>Search</button></form>
<form method="post" action="/exports"><button>Download selected ZIP</button>
{% for r in rows %}<label><input type="checkbox" name="document_ids" value="{{r['id']}}"> Select</label><a href="/documents/{{r['id']}}">{{r['title']}}</a>{% endfor %}</form>
{% if next_url %}<a href="{{next_url}}">Next page</a>{% endif %}'''


def browser_listing(db, cid=None):
    """Browser search: same rules as the API; paginates 25 per page from step 9."""
    params = {'q': request.args.get('q', '')}
    if cid:
        params['collection_id'] = cid
    if STEP >= 9:
        for key in ('kind', 'title_prefix', 'cursor'):
            if request.args.get(key):
                params[key] = request.args[key]
        params['page_size'] = '25'
    try:
        result = listing(db, 'search', params)
    except Invalid:
        abort(400)
    if isinstance(result, list):
        return result, None
    next_url = None
    if result['next_cursor']:
        next_url = '?' + urllib.parse.urlencode({k: v for k, v in params.items() if k not in {'page_size', 'collection_id'}} | {'cursor': result['next_cursor']})
    return result['items'], next_url


@app.get('/')
def library():
    uid = session.get('uid')
    if not uid:
        return '<a href="/login">Log in</a> <a href="/register">Create account</a>'
    with conn() as db:
        rows, next_url = browser_listing(db)
        colls = db.execute('SELECT * FROM collections').fetchall()
        colls = [c for c in colls if role(db, c['id'], uid)]
        return render_template_string(nav() + LIBRARY + '{% for c in colls %}<a href="/collections/{{c["id"]}}">{{c["name"]}}</a>{% endfor %}',
                                      heading='My library', rows=rows, colls=colls, step=STEP, q=request.args.get('q', ''),
                                      prefix=request.args.get('title_prefix', ''), next_url=next_url)


@app.route('/new/note', methods=['GET', 'POST'])
def browser_new():
    identity()
    if request.method == 'POST':
        with conn() as db:
            content = request.form.get('content', '')
            create_document(db, identity(), None, request.form['title'], '', 'note.txt', 'note', content, content.encode())
        return redirect('/')
    return '<form method="post"><input name="title"><textarea name="content"></textarea><button>Save</button></form>'


@app.route('/new/file', methods=['GET', 'POST'])
def browser_upload():
    identity()
    if request.method == 'POST':
        file = request.files['file']
        data = file.read()
        with conn() as db:
            create_document(db, identity(), None, request.form['title'], '', file.filename, 'file', '', data)
        return redirect('/')
    return '<form method="post" enctype="multipart/form-data"><input name="title"><input type="file" name="file"><button>Save document</button></form>'


DETAIL = '''<h1>{{title}}</h1><p>{{description}}</p><article>{{content}}</article>
<a href="/documents/{{id}}/edit">Edit document</a><a href="/documents/{{id}}/download">Download</a>
{% if step >= 7 %}<a href="/documents/{{id}}/history">History</a>{% endif %}
{% if state=='active' %}<form method="post" action="/documents/{{id}}/archive"><button>Archive document</button></form>
{% else %}<form method="post" action="/documents/{{id}}/restore"><button>Restore document</button></form>{% endif %}
{% if manage_links %}<section><h2>Client links</h2>
<form method="post" action="/documents/{{id}}/shares"><label>Lifetime in seconds<input name="expires_in_seconds" type="number" value="3600"></label><button>Create client link</button></form>
<ul>{% for s in shares %}<li><code>{{s.url}}</code> expires {{s.expires_at}} {% if s.revoked %}revoked{% else %}
<form method="post" action="/shares/{{s.id}}/revoke"><button>Revoke link</button></form>{% endif %}</li>{% endfor %}</ul></section>{% endif %}'''


@app.get('/documents/<did>')
def browser_detail(did):
    with conn() as db:
        row = document_row(db, did)
        manage = STEP >= 5 and row['state'] == 'active' and permitted(db, row, identity(), 'owner')
        shares = [share_json(s, True) for s in db.execute('SELECT * FROM shares WHERE document_id=?', (did,))] if manage else []
        return render_template_string(nav() + DETAIL, step=STEP, manage_links=manage, shares=shares, **dict(row))


@app.route('/documents/<did>/edit', methods=['GET', 'POST'])
def browser_edit(did):
    with conn() as db:
        row = document_row(db, did, 'write')
        if request.method == 'POST':
            value = {'title': request.form['title']}
            if row['kind'] == 'note':
                value['content'] = request.form.get('content', row['content'])
            if apply_patch(db, row, identity(), value):
                abort(400)
            return redirect('/documents/' + did)
        return render_template_string('<form method="post"><input name="title" value="{{title}}"><textarea name="content">{{content}}</textarea><button>Save changes</button></form>', **dict(row))


@app.get('/documents/<did>/download')
def browser_download(did):
    with conn() as db:
        row = document_row(db, did)
        return send_file(io.BytesIO(row['bytes']), as_attachment=True, download_name=row['filename'])


@app.post('/documents/<did>/archive')
def browser_archive_document(did):
    with conn() as db:
        document_row(db, did, 'owner')
        set_state(db, did, 'archived')
    return redirect('/archive')


@app.post('/documents/<did>/restore')
def browser_restore_document(did):
    with conn() as db:
        document_row(db, did, 'owner')
        set_state(db, did, 'active')
    return redirect('/documents/' + did)


@app.post('/documents/<did>/shares')
def browser_share(did):
    with conn() as db:
        row = share_manager(db, did)
        try:
            lifetime = int(request.form.get('expires_in_seconds', ''))
        except ValueError:
            abort(400)
        share, _ = create_share(db, row, lifetime)
        if share is None:
            abort(400)
    return redirect('/documents/' + did)


@app.post('/shares/<sid>/revoke')
def browser_revoke(sid):
    with conn() as db:
        share = db.execute('SELECT * FROM shares WHERE id=?', (sid,)).fetchone()
        if share is None:
            abort(404)
        share_manager(db, share['document_id'])
        db.execute('UPDATE shares SET revoked=1 WHERE id=?', (sid,))
    return redirect('/documents/' + share['document_id'])


@app.get('/documents/<did>/history')
def browser_history(did):
    with conn() as db:
        row = history_document(db, did)
        revisions = db.execute('SELECT * FROM revisions WHERE document_id=? ORDER BY number', (did,)).fetchall()
        owner = row['state'] == 'active' and permitted(db, row, identity(), 'owner')
        return render_template_string(nav() + '''<h1>History of {{row['title']}}</h1><ol>{% for r in revisions %}<li>Revision {{r['number']}}: {{r['title']}}
        <a href="/api/documents/{{row['id']}}/revisions/{{r['number']}}/download">Download revision {{r['number']}}</a>
        {% if owner %}<form method="post" action="/documents/{{row['id']}}/revisions/{{r['number']}}/restore"><button>Restore revision {{r['number']}}</button></form>{% endif %}</li>{% endfor %}</ol>''',
                                      row=row, revisions=revisions, owner=owner)


@app.post('/documents/<did>/revisions/<int:number>/restore')
def browser_revision_restore(did, number):
    with conn() as db:
        if restore_revision(db, did, number) != 200:
            abort(403)
    return redirect('/documents/' + did + '/history')


@app.post('/exports')
def browser_export():
    with conn() as db:
        rows = export_rows(db, request.form.getlist('document_ids'))
        if rows is None:
            abort(400)
        return zip_response(rows)


@app.route('/imports/new', methods=['GET', 'POST'])
def browser_import():
    uid = identity()
    with conn() as db:
        if request.method == 'POST':
            jid, _ = create_import(db, uid, {'url': request.form.get('url', ''), 'title': request.form.get('title', ''),
                                             'description': request.form.get('description', ''),
                                             'collection_id': request.form.get('collection_id') or None})
            if jid is None:
                abort(400)
        colls = [c for c in db.execute('SELECT * FROM collections').fetchall() if role(db, c['id'], uid) in {'owner', 'editor'}]
    if request.method == 'POST':
        start_job(jid)
        return redirect('/imports/' + jid)
    return render_template_string(nav() + '''<h1>Import from URL</h1><form method="post"><label>URL<input name="url" type="url"></label>
    <label>Title<input name="title"></label><label>Description<textarea name="description"></textarea></label>
    <label>Location<select name="collection_id"><option value="">My library</option>{% for c in colls %}<option value="{{c['id']}}">{{c['name']}}</option>{% endfor %}</select></label>
    <button>Start import</button></form>''', colls=colls)


@app.get('/imports/<jid>')
def browser_job(jid):
    with conn() as db:
        job = owned_job(db, jid)
    return render_template_string(nav() + '''<h1>Import {{job['title']}}</h1><p>Status: {{job['status']}}</p>
    {% if job['error'] %}<p>Error: {{job['error']}}</p>{% endif %}
    {% if job['status'] == 'failed' %}<form method="post" action="/imports/{{job['id']}}/retry"><button>Retry import</button></form>{% endif %}
    {% if job['document_id'] %}<a href="/documents/{{job['document_id']}}">Open document</a>{% endif %}''', job=job)


@app.post('/imports/<jid>/retry')
def browser_retry(jid):
    with conn() as db:
        status = retry_job(db, owned_job(db, jid))
    if status != 202:
        abort(400)
    start_job(jid)
    return redirect('/imports/' + jid)


COLLECTION = '''<h1>{{name}}</h1><p>Members and collaborators</p>
{% for r in rows %}<p>{{r["title"]}}</p>{% endfor %}
{% if transfer %}<form method="post" action="/collections/{{cid}}/transfer" onsubmit="return confirm('Transfer ownership?')">
<label>New owner email<input name="new_owner_email" type="email"></label>
<label><input type="checkbox" name="retain_former_owner" value="1"> Keep me as editor</label><button>Transfer ownership</button></form>{% endif %}
<form method="post"><input name="email" aria-label="Email"><select name="role"><option value="reader">Reader</option><option value="editor">Editor</option></select><button>Save member</button></form>'''


@app.get('/collections/<cid>')
def browser_collection(cid):
    with conn() as db:
        rows = selected_documents(db, cid)
        coll = db.execute('SELECT * FROM collections WHERE id=?', (cid,)).fetchone()
        owner = role(db, cid, identity()) == 'owner'
        return render_template_string(COLLECTION, rows=rows, name=coll['name'], cid=cid, transfer=STEP >= 10 and owner)


@app.post('/collections/<cid>')
def browser_add_member(cid):
    with conn() as db:
        if role(db, cid, identity()) != 'owner':
            abort(403)
        status, _ = put_member(db, cid, request.form.get('email'), request.form.get('role'))
        if status != 200:
            abort(status)
    return redirect('/collections/' + cid)


@app.post('/collections/<cid>/transfer')
def browser_transfer(cid):
    if STEP < 10:
        abort(404)
    with conn() as db:
        status, _ = do_transfer(db, cid, identity(), request.form.get('new_owner_email', ''),
                                request.form.get('retain_former_owner') == '1')
    if status != 200:
        abort(status)
    return redirect('/')


@app.get('/archive')
def browser_archive():
    with conn() as db:
        rows = selected_documents(db, state='archived')
        return render_template_string(nav() + '<h1>Archive</h1>{% for r in rows %}<a href="/documents/{{r["id"]}}">{{r["title"]}}</a>{% endfor %}', rows=rows)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8123, threaded=True)

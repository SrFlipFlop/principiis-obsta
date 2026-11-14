"""Evaluator-only controls; never delivered as benchmark solutions."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import sqlite3
import sys
from urllib.request import urlopen

mode = sys.argv[1]
items = {'alice': 'Alice document', 'bob': 'Bob private document'}
database = sqlite3.connect(':memory:')
database.execute('CREATE TABLE documents (owner TEXT PRIMARY KEY, body TEXT)')
database.executemany('INSERT INTO documents VALUES (?, ?)', items.items())
def read(owner):
    if mode == 'alternative':
        row = database.execute('SELECT body FROM documents WHERE owner = ?', (owner,)).fetchone()
        return row[0] if row else ''
    return items.get(owner, '')
def write(owner, body):
    if mode == 'alternative':
        database.execute('UPDATE documents SET body = ? WHERE owner = ?', (body, owner))
    else:
        items[owner] = body
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/ready':
            self.send_response(200); self.end_headers(); return
        if self.path == '/':
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers()
            self.wfile.write(b'''<form id="login"><input aria-label="User" id="user"><button>Login</button></form><div id="result"></div><script>login.onsubmit=async e=>{e.preventDefault();let r=await fetch('/document/'+user.value,{headers:{'X-User':user.value}});result.textContent=await r.text()}</script>'''); return
        owner = self.path.rsplit('/', 1)[-1]
        authorized = self.headers.get('X-User') == owner
        if mode == 'reject-all' or (mode != 'ui-only' and not authorized):
            self.send_response(403); self.end_headers(); return
        self.send_response(200); self.end_headers(); self.wfile.write(read(owner).encode())
    def do_POST(self):
        owner = self.path.rsplit('/', 1)[-1]
        authorized = self.headers.get('X-User') == owner
        if mode == 'reject-all' or (mode != 'ui-only' and not authorized):
            self.send_response(403); self.end_headers(); return
        write(owner, self.rfile.read(int(self.headers['Content-Length'])).decode())
        with urlopen('http://127.0.0.1:8124/audit', data=b'updated') as response:
            response.read()
        self.send_response(200); self.end_headers()
HTTPServer(('127.0.0.1', 8123), Handler).serve_forever()

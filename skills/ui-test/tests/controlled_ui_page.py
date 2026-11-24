"""Loopback-only browser fixture. Requests and counters are scoped to one server."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread

_PAGE = """<!doctype html><html lang="en"><title>Controlled UI</title>
<h1>Case workspace</h1><p id="identity">Signed in as local tester</p>
<label>Title <input id="title"></label><button id="submit">Submit</button>
<button id="status">Check status</button>
<p id="receipt"></p><span data-ui-sensitive style="position:absolute;top:180px;left:50px">private fixture identity</span><output id="result"></output><script>
document.querySelector('#status').onclick = async () => {
  const response = await fetch('/status');
  const data = await response.json();
  document.querySelector('#result').textContent = data.ready ? 'Available' : 'Unavailable';
};
document.querySelector('#submit').onclick = async () => {
  document.querySelector('#result').textContent = '';
  const response = await fetch('/submit', {method:'POST', body:document.querySelector('#title').value});
  const data = await response.json();
  document.querySelector('#receipt').textContent = data.saved ? 'Server accepted ' + document.querySelector('#title').value : 'Server rejected';
  setTimeout(() => { document.querySelector('#result').textContent = data.saved ? 'Saved' : 'Rejected'; }, 500);
};
</script></html>"""


@contextmanager
def controlled_page(*, response_headers=()):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, content_type, content):
            body = content.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            for name, value in response_headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            requests.append(('GET', self.path))
            if self.path == '/case':
                self.reply(200, 'text/html; charset=utf-8', _PAGE)
            elif self.path == '/status':
                self.reply(200, 'application/json', '{"ready":true,"private":"private-fixture-value"}')
            else:
                self.reply(404, 'text/plain', '')

        def do_POST(self):
            requests.append(('POST', self.path))
            if self.path != '/submit':
                self.reply(404, 'text/plain', '')
                return
            value = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            self.reply(200, 'application/json', json.dumps({'saved': bool(value.strip())}))

    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f'http://127.0.0.1:{server.server_port}/case', requests
        finally:
            server.shutdown()
            worker.join()

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from fe_maker import __main__ as launcher


def _server(post_status: int) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(post_status)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_a_running_build_keeps_the_server():
    server = _server(409)
    try:
        port = server.server_address[1]
        assert launcher._stop_running(f"http://127.0.0.1:{port}", port) == "busy"
    finally:
        server.shutdown()
        server.server_close()


def test_a_stopped_server_frees_its_port():
    server = _server(200)
    port = server.server_address[1]
    server.shutdown()
    server.server_close()     # what the running FE Maker does once asked to stop
    assert launcher._stop_running(f"http://127.0.0.1:{port}", port) == "stopped"

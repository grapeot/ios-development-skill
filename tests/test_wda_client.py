import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "wda_client.py"
spec = importlib.util.spec_from_file_location("wda_client", MODULE)
wda = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wda)


class ClientTests(unittest.TestCase):
    def test_rejects_missing_host_and_embedded_credentials(self):
        for url in ["file:///tmp/test", "http://", "http://user:secret@example.com", "http://localhost:8100?token=x"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                wda.Client(url)

    def test_read_without_session_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Open a session"):
            wda.Client("http://127.0.0.1:8100").request("GET", "/source")

    def test_session_does_not_reset_or_terminate_existing_app(self):
        c = wda.Client("http://127.0.0.1:8100")
        with patch.object(c, "request", return_value={"value": {"sessionId": "test-session"}}) as request:
            self.assertEqual(c.open("com.example.app"), "test-session")
        args = request.call_args.args
        self.assertEqual(args[:2], ("POST", "/session"))
        caps = args[2]["capabilities"]["alwaysMatch"]
        self.assertFalse(caps["shouldTerminateApp"])
        self.assertFalse(caps["forceAppLaunch"])
        self.assertNotIn("app", caps)

    def test_typing_transmits_unicode_without_implicit_clear(self):
        c = wda.Client("http://127.0.0.1:8100", "test-session")
        with patch.object(c, "request", return_value={}) as request:
            c.type("element-1", "Hello 中文")
        request.assert_called_once_with("POST", "/element/element-1/value", {"value": list("Hello 中文")})

    def test_clear_is_separate_explicit_operation(self):
        c = wda.Client("http://127.0.0.1:8100", "test-session")
        with patch.object(c, "request", return_value={}) as request:
            c.type("element-1", "text", clear=True)
        self.assertEqual(request.call_args_list[0].args, ("POST", "/element/element-1/clear", {}))

    def test_private_artifact_permissions_even_when_replacing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "capture.json"
            p.write_text("old")
            p.chmod(0o644)
            wda.save_private(p, b'{"synthetic":true}')
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            self.assertTrue(json.loads(p.read_text())["synthetic"])

    def test_missing_parent_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "parent"):
                wda.save_private(Path(directory) / "missing" / "capture", b"data")

    def test_refuses_symlink_output(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "original"
            target.write_bytes(b"keep")
            link = Path(directory) / "alias"
            link.symlink_to(target)
            with self.assertRaises(OSError):
                wda.save_private(link, b"replace")
            self.assertEqual(target.read_bytes(), b"keep")


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        requests = self.requests

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else None
                requests.append((self.command, self.path, body))
                if self.path == "/wda/shutdown":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"Shutting down")
                    return
                if self.path.endswith("/missing"):
                    code, payload = 404, {"value": {"error": "no such element", "message": "synthetic missing element"}}
                elif self.path == "/status":
                    code, payload = 200, {"value": {"ready": True}}
                else:
                    code, payload = 200, {"value": {"accepted": True}}
                data = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = respond

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.client = wda.Client(f"http://127.0.0.1:{self.server.server_port}", "synthetic-session")

    def test_status_without_session_and_session_route(self):
        self.assertTrue(self.client.request("GET", "/status", session=False)["value"]["ready"])
        self.client.click("element-1")
        self.assertEqual(self.requests[1], ("POST", "/session/synthetic-session/element/element-1/click", {}))

    def test_preserves_remote_error_code_and_message(self):
        with self.assertRaises(wda.WDAError) as error:
            self.client.request("GET", "/missing")
        self.assertEqual(error.exception.status, 404)
        self.assertEqual(error.exception.error, "no such element")
        self.assertIn("synthetic missing", str(error.exception))

    def test_upstream_plain_text_shutdown_response(self):
        self.assertIsNone(self.client.request("GET", "/wda/shutdown", session=False)["value"])


if __name__ == "__main__":
    unittest.main()

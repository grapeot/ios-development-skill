#!/usr/bin/env python3
"""Small standard-library client for an already running WebDriverAgent.

Connection/session state and captured UI data belong outside this repository.
This client does not build WDA, install apps, reset app data, or change settings.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import ProxyHandler, Request, build_opener


class WDAError(RuntimeError):
    def __init__(self, status, error, message):
        self.status, self.error = status, error
        super().__init__(message)


class Client:
    def __init__(self, url, session=None, timeout=30):
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("WDA URL must be an explicit HTTP(S) endpoint")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("WDA URL must not contain credentials, query, or fragment")
        self.url = url.rstrip("/")
        self.session = session
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        self.timeout = timeout
        # Device tunnels must not be routed through ambient HTTP proxies.
        self.opener = build_opener(ProxyHandler({}))

    def request(self, method, path, body=None, session=True):
        if session:
            if not self.session:
                raise ValueError("Open a session first or provide a saved session file")
            path = "/session/" + quote(self.session, safe="") + path
        data = None if body is None else json.dumps(body).encode()
        req = Request(self.url + path, data=data, method=method,
                      headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read()
                # This upstream route deliberately returns text, not WebDriver JSON.
                if not session and path == "/wda/shutdown" and raw.strip() == b"Shutting down":
                    return {"value": None}
                payload = json.loads(raw)
        except HTTPError as error:
            try:
                payload = json.load(error)
            except (ValueError, UnicodeError):
                raise WDAError(error.code, "http_error", error.reason) from error
            value = payload.get("value", {})
            raise WDAError(error.code, value.get("error", "http_error"),
                           value.get("message", error.reason)) from error
        value = payload.get("value")
        if isinstance(value, dict) and value.get("error"):
            raise WDAError(200, value["error"], value.get("message", "WDA error"))
        return payload

    def open(self, bundle):
        payload = self.request("POST", "/session", {"capabilities": {"alwaysMatch": {
            "bundleId": bundle, "shouldWaitForQuiescence": False,
            "shouldTerminateApp": False, "forceAppLaunch": False,
        }}}, session=False)
        self.session = payload.get("sessionId") or payload.get("value", {}).get("sessionId")
        if not self.session:
            raise ValueError("WDA did not return a session ID")
        return self.session

    def find(self, using, value):
        return self.request("POST", "/elements", {"using": using, "value": value})["value"]

    def click(self, element):
        return self.request("POST", "/element/" + quote(element, safe="") + "/click", {})

    def type(self, element, text, clear=False):
        path = "/element/" + quote(element, safe="")
        if clear:
            self.request("POST", path + "/clear", {})
        return self.request("POST", path + "/value", {"value": list(text)})


def save_private(path, data):
    path = Path(path)
    if not path.parent.is_dir():
        raise ValueError("Create the output parent directory before saving")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("WDA_URL"))
    parser.add_argument("--session-file", type=Path)
    parser.add_argument("--timeout", type=float, default=30)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("shutdown")
    op = sub.add_parser("open")
    op.add_argument("--bundle-id", required=True)
    sub.add_parser("close")
    src = sub.add_parser("source")
    src.add_argument("--output", required=True, type=Path)
    find = sub.add_parser("find")
    find.add_argument("--using", default="accessibility id",
                      choices=["accessibility id", "predicate string", "class chain", "class name", "xpath"])
    find.add_argument("--value", required=True)
    click = sub.add_parser("click")
    click.add_argument("--element", required=True)
    tap = sub.add_parser("tap")
    tap.add_argument("--x", required=True, type=float)
    tap.add_argument("--y", required=True, type=float)
    keys = sub.add_parser("keys")
    keys.add_argument("--text-file", required=True, type=Path)
    typ = sub.add_parser("type")
    typ.add_argument("--element", required=True)
    typ.add_argument("--text-file", required=True, type=Path)
    typ.add_argument("--clear", action="store_true")
    shot = sub.add_parser("screenshot")
    shot.add_argument("--output", required=True, type=Path)
    swipe = sub.add_parser("swipe")
    swipe.add_argument("--direction", required=True, choices=["up", "down", "left", "right"])
    activate = sub.add_parser("activate")
    activate.add_argument("--bundle-id", required=True)
    args = parser.parse_args()
    try:
        if not args.url:
            raise ValueError("Set WDA_URL or --url to the verified device endpoint")
        session = None
        if args.session_file and args.session_file.exists():
            saved = json.loads(args.session_file.read_text())
            if saved["url"] != args.url.rstrip("/"):
                raise ValueError("Saved session belongs to a different endpoint")
            session = saved["session_id"]
        client = Client(args.url, session, args.timeout)
        if args.command == "status":
            value = client.request("GET", "/status", session=False)["value"]
            result = {"ready": value.get("ready"), "state": value.get("state"),
                      "version": value.get("build", {}).get("version")}
        elif args.command == "shutdown":
            client.request("GET", "/wda/shutdown", session=False)
            if args.session_file:
                args.session_file.unlink(missing_ok=True)
            result = {"shutdown_requested": True}
        elif args.command == "open":
            if not args.session_file:
                raise ValueError("open requires --session-file outside the repository")
            client.open(args.bundle_id)
            save_private(args.session_file, json.dumps({"url": client.url, "session_id": client.session}).encode())
            result = {"opened": True, "session_file": str(args.session_file)}
        elif args.command == "find":
            result = {"elements": client.find(args.using, args.value)}
        elif args.command == "click":
            client.click(args.element)
            result = {"clicked": True}
        elif args.command == "tap":
            if args.x < 0 or args.y < 0:
                raise ValueError("Tap coordinates must be non-negative screen points")
            client.request("POST", "/wda/tap", {"x": args.x, "y": args.y})
            result = {"tapped": True}
        elif args.command == "keys":
            client.request("POST", "/wda/keys", {"value": list(args.text_file.read_text())})
            result = {"typed": True}
        elif args.command == "type":
            # Deliberately do not put passwords, OTPs, or entered text in argv/output.
            client.type(args.element, args.text_file.read_text(), args.clear)
            result = {"typed": True}
        elif args.command == "source":
            value = client.request("GET", "/source?format=json")["value"]
            save_private(args.output, json.dumps(value, ensure_ascii=False, indent=2).encode())
            result = {"saved": str(args.output)}
        elif args.command == "screenshot":
            value = client.request("GET", "/screenshot")["value"]
            save_private(args.output, base64.b64decode(value, validate=True))
            result = {"saved": str(args.output)}
        elif args.command == "swipe":
            client.request("POST", "/wda/swipe", {"direction": args.direction})
            result = {"swiped": True}
        elif args.command == "activate":
            client.request("POST", "/wda/apps/activate", {"bundleId": args.bundle_id})
            result = {"activated": True}
        else:
            client.request("DELETE", "")
            if args.session_file:
                args.session_file.unlink(missing_ok=True)
            result = {"closed": True}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except WDAError as error:
        print(json.dumps({"error": error.error, "status": error.status, "message": str(error)}))
    except Exception as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Zero-configuration local Connector for the Janson Dashboard.

The runtime intentionally uses Python's standard library.  It keeps video
files and provider keys local, opens a one-time pairing page, and relays only
the V1 command allowlist over an outbound WebSocket.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import secrets
import socket
import ssl
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from scripts.local_connector_protocol import CommandPolicy, ReconnectBackoff


class ConnectorRuntimeError(RuntimeError):
    pass


class CredentialStore(Protocol):
    def get(self) -> str | None: ...
    def set(self, credential: str) -> None: ...
    def delete(self) -> None: ...


class MemoryCredentialStore:
    def __init__(self) -> None:
        self._credential: str | None = None

    def get(self) -> str | None:
        return self._credential

    def set(self, credential: str) -> None:
        self._credential = credential

    def delete(self) -> None:
        self._credential = None


class MacOSKeychainStore:
    """Store only the Connector credential in the macOS login Keychain."""

    service = "awesome-janson-local-connector"
    account = "default"

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["security", *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def get(self) -> str | None:
        result = self._run("find-generic-password", "-a", self.account, "-s", self.service, "-w")
        return result.stdout.strip() if result.returncode == 0 else None

    def set(self, credential: str) -> None:
        result = self._run("add-generic-password", "-U", "-a", self.account, "-s", self.service, "-w", credential)
        if result.returncode != 0:
            raise ConnectorRuntimeError("無法把剪神連線憑證存入 macOS Keychain")

    def delete(self) -> None:
        self._run("delete-generic-password", "-a", self.account, "-s", self.service)


class JsonTransport:
    def __init__(self, timeout: float = 15) -> None:
        self.timeout = timeout

    def request(self, url: str, method: str = "GET", body: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            method=method,
            headers={"accept": "application/json", "user-agent": "Janson-Connector/0.1", **(headers or {})},
        )
        if payload is not None:
            request.add_header("content-type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                body = json.loads(error.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = {"error": {"code": f"HTTP_{error.code}"}}
            raise ConnectorRuntimeError(body.get("error", {}).get("code", f"HTTP_{error.code}")) from error
        except urllib.error.URLError as error:
            raise ConnectorRuntimeError(f"CLOUD_UNAVAILABLE: {error.reason}") from error


class WebSocketClient:
    """Small RFC 6455 client for the Connector's outbound-only connection."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock

    @classmethod
    def connect(cls, url: str, headers: dict[str, str] | None = None, timeout: float = 15) -> "WebSocketClient":
        parsed = urlparse(url)
        if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
            raise ConnectorRuntimeError("WebSocket URL 必須使用 ws 或 wss")
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        raw = socket.create_connection((parsed.hostname, port), timeout=timeout)
        sock: socket.socket = raw
        if parsed.scheme == "wss":
            sock = ssl.create_default_context().wrap_socket(raw, server_hostname=parsed.hostname)
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        request_headers = {
            "Host": parsed.hostname if not parsed.port else f"{parsed.hostname}:{parsed.port}",
            "Upgrade": "websocket",
            "Connection": "Upgrade",
            "Sec-WebSocket-Key": key,
            "Sec-WebSocket-Version": "13",
            **(headers or {}),
        }
        request = "GET " + path + " HTTP/1.1\r\n" + "".join(f"{name}: {value}\r\n" for name, value in request_headers.items()) + "\r\n"
        sock.sendall(request.encode("ascii"))
        response = cls._read_headers(sock)
        if not response.startswith("HTTP/1.1 101") and not response.startswith("HTTP/2 101"):
            sock.close()
            raise ConnectorRuntimeError(f"WebSocket upgrade rejected: {response.splitlines()[0] if response else 'empty response'}")
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()).decode("ascii")
        if f"sec-websocket-accept: {expected.lower()}" not in response.lower():
            sock.close()
            raise ConnectorRuntimeError("WebSocket handshake validation failed")
        return cls(sock)

    @staticmethod
    def _read_headers(sock: socket.socket) -> str:
        data = bytearray()
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > 64 * 1024:
                raise ConnectorRuntimeError("WebSocket handshake headers too large")
        return bytes(data).decode("latin-1")

    def _read_exact(self, size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise ConnectorRuntimeError("WebSocket connection closed")
            data.extend(chunk)
        return bytes(data)

    def send_json(self, message: dict[str, Any]) -> None:
        self._send_frame(json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), opcode=0x1)

    def _send_frame(self, payload: bytes, opcode: int) -> None:
        mask = secrets.token_bytes(4)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        length = len(masked)
        if length < 126:
            header = bytes([0x80 | opcode, 0x80 | length])
        elif length < 65536:
            header = bytes([0x80 | opcode, 0x80 | 126]) + struct.pack("!H", length)
        else:
            header = bytes([0x80 | opcode, 0x80 | 127]) + struct.pack("!Q", length)
        self.sock.sendall(header + mask + masked)

    def recv_json(self, timeout: float | None = None) -> dict[str, Any]:
        self.sock.settimeout(timeout)
        while True:
            first, second = self._read_exact(2)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            if length > 32 * 1024:
                raise ConnectorRuntimeError("WebSocket message exceeds 32 KiB")
            mask = self._read_exact(4) if masked else b""
            payload = self._read_exact(length)
            if masked:
                payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
            if opcode == 0x8:
                raise ConnectorRuntimeError("WebSocket connection closed by server")
            if opcode == 0x9:
                self._send_frame(payload, opcode=0xA)
                continue
            if opcode == 0xA:
                continue
            if opcode != 0x1:
                raise ConnectorRuntimeError(f"Unsupported WebSocket opcode: {opcode}")
            try:
                return json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ConnectorRuntimeError("WebSocket message is not valid JSON") from error

    def close(self) -> None:
        try:
            self._send_frame(b"", opcode=0x8)
        except OSError:
            pass
        self.sock.close()


@dataclass
class ConnectorInfo:
    installation_id: str
    credential: str
    dashboard_url: str


class LocalConnector:
    def __init__(
        self,
        server_url: str,
        store: CredentialStore | None = None,
        transport: JsonTransport | None = None,
        opener: Callable[[str], bool] | None = None,
        client_version: str = "0.1.0",
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.store = store or (MacOSKeychainStore() if sys.platform == "darwin" else MemoryCredentialStore())
        self.transport = transport or JsonTransport()
        self.opener = opener or webbrowser.open
        self.client_version = client_version
        self.policy = CommandPolicy()

    def register(self) -> ConnectorInfo:
        response = self.transport.request(
            f"{self.server_url}/api/v1/installations",
            method="POST",
            body={"client_version": self.client_version, "platform": f"{platform.system().lower()}-{platform.machine()}"},
        )
        credential = response["connector_credential"]
        self.store.set(credential)
        return ConnectorInfo(response["installation_id"], credential, response["dashboard_url"])

    def pair(self, open_browser: bool = True) -> str:
        credential = self.store.get()
        if not credential:
            info = self.register()
            credential = info.credential
        response = self.transport.request(
            f"{self.server_url}/api/v1/pair-tickets",
            method="POST",
            headers={"authorization": f"Bearer {credential}"},
        )
        if open_browser:
            self.opener(response["dashboard_url"])
        return response["dashboard_url"]

    def connect(self, timeout: float = 15) -> WebSocketClient:
        credential = self.store.get()
        if not credential:
            self.register()
            credential = self.store.get()
        if not credential:
            raise ConnectorRuntimeError("Connector credential is missing")
        websocket_url = self.server_url.replace("https://", "wss://").replace("http://", "ws://") + "/api/v1/socket"
        return WebSocketClient.connect(websocket_url, {"Authorization": f"Bearer {credential}"}, timeout=timeout)

    def handle_command(self, command: dict[str, Any]) -> dict[str, Any]:
        self.policy.validate(command)
        if command["command"] == "connector.health":
            payload = {"version": self.client_version, "platform": platform.system().lower(), "capabilities": ["connector.health", "job.echo"]}
        else:
            payload = {"message": command["payload"]["message"]}
        return {"v": 1, "type": "result", "command_id": command["command_id"], "status": "completed", "payload": payload, "error": None}

    def serve_once(self, timeout: float = 60) -> None:
        websocket = self.connect()
        try:
            websocket.send_json({"v": 1, "type": "ready", "event": "connector.ready"})
            end_at = time.monotonic() + timeout
            while time.monotonic() < end_at:
                command = websocket.recv_json(timeout=max(0.1, end_at - time.monotonic()))
                if command.get("type") != "command":
                    continue
                try:
                    websocket.send_json(self.handle_command(command))
                except Exception as error:  # noqa: BLE001 - convert all command failures to protocol results
                    websocket.send_json({"v": 1, "type": "result", "command_id": command.get("command_id"), "status": "failed", "payload": {}, "error": {"code": type(error).__name__}})
        finally:
            websocket.close()

    def serve_with_reconnect(self, stop: Callable[[], bool], max_attempts: int | None = None) -> None:
        backoff = ReconnectBackoff()
        attempts = 0
        while not stop():
            try:
                self.serve_once()
                backoff.reset()
            except (ConnectorRuntimeError, OSError):
                attempts += 1
                if max_attempts is not None and attempts >= max_attempts:
                    raise
                time.sleep(backoff.next_delay())


def main() -> int:
    parser = argparse.ArgumentParser(description="剪神本機 Connector")
    parser.add_argument("--server-url", default=os.environ.get("JANSON_DASHBOARD_URL", "https://awesome-janson-dashboard.pages.dev"))
    parser.add_argument("--no-open", action="store_true", help="只取得配對網址，不開瀏覽器")
    parser.add_argument("--serve-once", action="store_true", help="連線並服務一個測試工作階段")
    args = parser.parse_args()
    connector = LocalConnector(args.server_url)
    dashboard_url = connector.pair(open_browser=not args.no_open)
    print(f"Dashboard pairing URL: {dashboard_url}")
    if args.serve_once:
        connector.serve_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

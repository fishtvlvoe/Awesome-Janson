#!/usr/bin/env python3
"""Bounded live staging/prod smoke test for two anonymous installations."""

from __future__ import annotations

import json
import os
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse
import urllib.request

from scripts.local_connector import JsonTransport, LocalConnector, MemoryCredentialStore, WebSocketClient, ConnectorRuntimeError


BASE = os.environ.get("JANSON_E2E_BASE", "https://d889760b.awesome-janson-dashboard.pages.dev")


def exchange(ticket_url: str) -> str:
    ticket = parse_qs(urlparse(ticket_url).fragment.removeprefix("/connect?")).get("ticket", [""])[0]
    request = urllib.request.Request(
        f"{BASE}/api/v1/pair/exchange",
        data=json.dumps({"ticket": ticket}).encode("utf-8"),
        method="POST",
        headers={"content-type": "application/json", "user-agent": "Janson-Connector-E2E/0.1", "accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        return cookie["janson_session"].value


def command(cookie: str, command_id: str, name: str, payload: dict) -> dict:
    transport = JsonTransport()
    return transport.request(
        f"{BASE}/api/v1/command",
        method="POST",
        headers={"cookie": f"janson_session={cookie}"},
        body={"v": 1, "type": "command", "command_id": command_id, "command": name, "payload": payload},
    )


def provision():
    connector = LocalConnector(BASE, store=MemoryCredentialStore(), opener=lambda _url: True)
    pairing_url = connector.pair(open_browser=False)
    session_cookie = exchange(pairing_url)
    return connector, session_cookie


def main() -> int:
    connector_a, cookie_a = provision()
    connector_b, cookie_b = provision()
    socket_a = connector_a.connect()
    socket_b = connector_b.connect()
    socket_a.send_json({"v": 1, "type": "ready", "event": "connector.ready"})
    socket_b.send_json({"v": 1, "type": "ready", "event": "connector.ready"})
    dashboard_a = WebSocketClient.connect(BASE.replace("https://", "wss://") + "/api/v1/socket", {"Cookie": f"janson_session={cookie_a}"})
    dashboard_b = WebSocketClient.connect(BASE.replace("https://", "wss://") + "/api/v1/socket", {"Cookie": f"janson_session={cookie_b}"})
    dashboard_c = WebSocketClient.connect(BASE.replace("https://", "wss://") + "/api/v1/socket", {"Cookie": f"janson_session={cookie_a}"})
    dashboard_d = WebSocketClient.connect(BASE.replace("https://", "wss://") + "/api/v1/socket", {"Cookie": f"janson_session={cookie_a}"})
    try:
        try:
            WebSocketClient.connect(BASE.replace("https://", "wss://") + "/api/v1/socket", {"Cookie": f"janson_session={cookie_a}"})
        except ConnectorRuntimeError as error:
            assert "429" in str(error)
        else:
            raise AssertionError("fourth dashboard connection was accepted")
        accepted = command(cookie_a, "live-health-a", "connector.health", {})
        assert accepted["accepted"] is True
        health = socket_a.recv_json(timeout=10)
        assert health["command_id"] == "live-health-a"
        socket_a.send_json(connector_a.handle_command(health))
        result = dashboard_a.recv_json(timeout=10)
        assert result["payload"]["capabilities"] == ["connector.health", "job.echo"]
        command(cookie_a, "cross-tenant-a", "job.echo", {"message": "only A"})
        received_a = socket_a.recv_json(timeout=10)
        assert received_a["payload"]["message"] == "only A"
        socket_a.send_json(connector_a.handle_command(received_a))
        dashboard_a.recv_json(timeout=10)
        try:
            dashboard_b.sock.settimeout(0.5)
            dashboard_b.recv_json(timeout=0.5)
            raise AssertionError("tenant B unexpectedly received tenant A event")
        except (TimeoutError, OSError, ConnectorRuntimeError):
            pass

        socket_a.close()
        try:
            command(cookie_a, "offline-a", "connector.health", {})
        except ConnectorRuntimeError as error:
            assert "CONNECTOR_OFFLINE" in str(error)
        else:
            raise AssertionError("offline command was accepted")
    finally:
        socket_b.close()
        dashboard_a.close()
        dashboard_b.close()
        dashboard_c.close()
        dashboard_d.close()
    print("LIVE E2E PASS: two installations isolated, health round-trip, offline rejection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

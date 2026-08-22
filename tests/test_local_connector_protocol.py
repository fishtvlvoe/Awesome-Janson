"""Phase 2 red tests for the Dashboard ↔ local Connector protocol.

These tests intentionally describe the public protocol model before its
implementation exists.  Keep this file dependency-free so it can run in the
existing unittest suite and in the future local Connector test harness.
"""

from __future__ import annotations

import unittest
import importlib


class LocalConnectorProtocolTests(unittest.TestCase):
    def protocol(self):
        try:
            return importlib.import_module("scripts.local_connector_protocol")
        except ModuleNotFoundError as error:
            self.fail(f"RED: local Connector protocol implementation is missing: {error}")

    def test_tenant_a_cannot_reach_tenant_b(self) -> None:
        protocol = self.protocol()
        router = protocol.TenantRouter()
        router.register_installation("ins_B", "credential-B")
        session_a = router.dashboard_session("ins_A", "session-A")
        connector_b = router.connector_session("ins_B", "credential-B")

        with self.assertRaises(protocol.TenantMismatchError):
            router.route_command(session_a, connector_b, {"command": "job.echo"})

    def test_pair_ticket_is_single_use(self) -> None:
        protocol = self.protocol()
        store = protocol.PairTicketStore(now=lambda: 100.0)
        ticket = store.issue("ins_A")

        self.assertEqual(store.exchange(ticket, now=101.0), "ins_A")
        with self.assertRaises(protocol.PairTicketUsedError):
            store.exchange(ticket, now=102.0)

    def test_expired_pair_ticket_is_rejected(self) -> None:
        protocol = self.protocol()
        store = protocol.PairTicketStore(now=lambda: 100.0, ttl_seconds=120)
        ticket = store.issue("ins_A")

        with self.assertRaises(protocol.PairTicketExpiredError):
            store.exchange(ticket, now=220.001)

    def test_forged_connector_credential_is_rejected(self) -> None:
        protocol = self.protocol()
        router = protocol.TenantRouter()
        router.register_installation("ins_A", "real-secret")

        with self.assertRaises(protocol.InvalidConnectorCredentialError):
            router.connector_session("ins_A", "forged-secret")

    def test_unknown_command_never_reaches_connector(self) -> None:
        protocol = self.protocol()
        policy = protocol.CommandPolicy()
        command = {
            "v": 1,
            "type": "command",
            "command_id": "cmd-1",
            "command": "shell.exec",
            "payload": {"command": "rm -rf /"},
        }

        with self.assertRaises(protocol.UnknownCommandError):
            policy.validate(command)

    def test_oversized_payload_is_rejected(self) -> None:
        protocol = self.protocol()
        policy = protocol.CommandPolicy(max_message_bytes=32 * 1024)
        command = {
            "v": 1,
            "type": "command",
            "command_id": "cmd-oversized",
            "command": "job.echo",
            "payload": {"message": "x" * (32 * 1024)},
        }

        with self.assertRaises(protocol.PayloadTooLargeError):
            policy.validate(command)

    def test_sensitive_message_is_rejected(self) -> None:
        protocol = self.protocol()
        policy = protocol.CommandPolicy()
        command = {
            "v": 1,
            "type": "command",
            "command_id": "cmd-secret",
            "command": "job.echo",
            "payload": {"message": "ok", "api_key": "secret-value"},
        }

        with self.assertRaises(protocol.InvalidMessageError):
            policy.validate(command)

    def test_offline_connector_fails_without_queueing(self) -> None:
        protocol = self.protocol()
        room = protocol.RelayRoom("ins_A")
        dashboard = room.attach("dashboard", "dashboard-A")

        with self.assertRaises(protocol.ConnectorOfflineError):
            room.send_command(dashboard, {"command": "connector.health"})

        connector = room.attach("connector", "connector-A")
        self.assertEqual(room.received_commands(connector), [])

    def test_connector_reconnects_with_bounded_backoff(self) -> None:
        protocol = self.protocol()
        backoff = protocol.ReconnectBackoff(base_seconds=1, cap_seconds=30, jitter_ratio=0)

        delays = [backoff.next_delay() for _ in range(8)]

        self.assertEqual(delays, [1, 2, 4, 8, 16, 30, 30, 30])

    def test_new_connector_replaces_old_connection(self) -> None:
        protocol = self.protocol()
        room = protocol.RelayRoom("ins_A")
        old = room.attach("connector", "connector-old")
        new = room.attach("connector", "connector-new")

        self.assertTrue(new.is_authoritative)
        with self.assertRaises(protocol.ConnectionReplacedError):
            old.assert_authoritative()


if __name__ == "__main__":
    unittest.main()

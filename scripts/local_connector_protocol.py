"""Protocol primitives shared by the local Connector and test harness.

This module deliberately contains no network or video-processing code.  It
owns the small, deterministic rules that must remain identical on both sides
of the Dashboard ↔ local Connector boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import secrets
from typing import Any, Callable


class ConnectorProtocolError(Exception):
    """Base error for a rejected local Connector protocol operation."""


class TenantMismatchError(ConnectorProtocolError):
    pass


class InvalidConnectorCredentialError(ConnectorProtocolError):
    pass


class PairTicketUsedError(ConnectorProtocolError):
    pass


class PairTicketExpiredError(ConnectorProtocolError):
    pass


class UnknownCommandError(ConnectorProtocolError):
    pass


class PayloadTooLargeError(ConnectorProtocolError):
    pass


class InvalidMessageError(ConnectorProtocolError):
    pass


class ConnectorOfflineError(ConnectorProtocolError):
    pass


class ConnectionReplacedError(ConnectorProtocolError):
    pass


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _credential(installation_id: str, secret: str) -> str:
    return f"{installation_id}.{secret}"


def _split_credential(value: str) -> tuple[str, str]:
    installation_id, separator, secret = value.partition(".")
    if not separator or not installation_id or not secret:
        raise InvalidConnectorCredentialError("malformed credential")
    return installation_id, secret


@dataclass(frozen=True)
class ConnectorSession:
    installation_id: str
    credential: str
    role: str = "connector"
    is_authoritative: bool = True


@dataclass(frozen=True)
class DashboardSession:
    installation_id: str
    session_id: str
    role: str = "dashboard"


@dataclass
class _StoredTicket:
    installation_id: str
    digest: str
    expires_at: float
    used: bool = False


class PairTicketStore:
    """Single-use, short-lived pairing ticket store.

    The complete ticket is returned only to the caller that requested it.  The
    store keeps only its digest and never needs to persist the clear secret.
    """

    def __init__(
        self,
        now: Callable[[], float] | None = None,
        ttl_seconds: int = 120,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        self._now = now or __import__("time").time
        self._ttl_seconds = ttl_seconds
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._tickets: dict[str, _StoredTicket] = {}

    def issue(self, installation_id: str) -> str:
        secret = self._token_factory()
        ticket = _credential(installation_id, secret)
        self._tickets[ticket] = _StoredTicket(
            installation_id=installation_id,
            digest=_digest(secret),
            expires_at=self._now() + self._ttl_seconds,
        )
        return ticket

    def exchange(self, ticket: str, now: float | None = None) -> str:
        installation_id, secret = _split_credential(ticket)
        stored = self._tickets.get(ticket)
        current_time = self._now() if now is None else now
        if stored is None or stored.installation_id != installation_id:
            raise PairTicketExpiredError("pair ticket is unknown")
        if stored.used:
            raise PairTicketUsedError("pair ticket was already consumed")
        if current_time > stored.expires_at:
            raise PairTicketExpiredError("pair ticket has expired")
        if not secrets.compare_digest(stored.digest, _digest(secret)):
            raise PairTicketExpiredError("pair ticket is invalid")
        stored.used = True
        return installation_id


class TenantRouter:
    """Small in-memory model of the server-side tenant authority."""

    def __init__(self) -> None:
        self._credentials: dict[str, str] = {}

    def register_installation(self, installation_id: str, secret: str) -> str:
        self._credentials[installation_id] = _digest(secret)
        return _credential(installation_id, secret)

    def connector_session(self, installation_id: str, secret: str) -> ConnectorSession:
        stored = self._credentials.get(installation_id)
        if stored is None or not secrets.compare_digest(stored, _digest(secret)):
            raise InvalidConnectorCredentialError("credential rejected")
        return ConnectorSession(
            installation_id=installation_id,
            credential=_credential(installation_id, secret),
        )

    def dashboard_session(self, installation_id: str, session_id: str) -> DashboardSession:
        return DashboardSession(installation_id=installation_id, session_id=session_id)

    def route_command(
        self,
        dashboard: DashboardSession,
        connector: ConnectorSession,
        command: dict[str, Any],
    ) -> None:
        if dashboard.installation_id != connector.installation_id:
            raise TenantMismatchError("sessions belong to different installations")


_FORBIDDEN_KEYS = {
    "api_key",
    "apikey",
    "credential",
    "secret",
    "token",
    "signed_url",
    "path",
    "local_path",
    "shell",
    "subprocess",
}


class CommandPolicy:
    """Validate the V1 JSON command envelope and its small allowlist."""

    allowed_commands = frozenset({"connector.health", "job.echo"})

    def __init__(self, max_message_bytes: int = 32 * 1024) -> None:
        self.max_message_bytes = max_message_bytes

    def validate(self, command: dict[str, Any]) -> dict[str, Any]:
        try:
            encoded = json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise InvalidMessageError("command must be JSON serializable") from error
        if len(encoded) > self.max_message_bytes:
            raise PayloadTooLargeError("command exceeds the message limit")
        if not isinstance(command, dict) or command.get("v") != 1 or command.get("type") != "command":
            raise InvalidMessageError("invalid command envelope")
        if not isinstance(command.get("command_id"), str) or not command["command_id"]:
            raise InvalidMessageError("command_id is required")
        name = command.get("command")
        if name not in self.allowed_commands:
            raise UnknownCommandError(f"command is not allowed: {name}")
        payload = command.get("payload", {})
        if not isinstance(payload, dict):
            raise InvalidMessageError("payload must be an object")
        self._reject_forbidden_fields(payload)
        if name == "connector.health" and payload:
            raise InvalidMessageError("connector.health payload must be empty")
        if name == "job.echo" and not isinstance(payload.get("message"), str):
            raise InvalidMessageError("job.echo requires a string message")
        return command

    def _reject_forbidden_fields(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in _FORBIDDEN_KEYS:
                    raise InvalidMessageError(f"forbidden field: {key}")
                self._reject_forbidden_fields(child)
        elif isinstance(value, list):
            for child in value:
                self._reject_forbidden_fields(child)


@dataclass
class _RoomConnection:
    role: str
    connection_id: str
    is_authoritative: bool = True

    def assert_authoritative(self) -> None:
        if not self.is_authoritative:
            raise ConnectionReplacedError("connection was replaced")


class RelayRoom:
    """Deterministic in-memory model for one installation's relay room."""

    def __init__(self, installation_id: str) -> None:
        self.installation_id = installation_id
        self._connections: dict[str, _RoomConnection] = {}
        self._received: dict[str, list[dict[str, Any]]] = {}

    def attach(self, role: str, connection_id: str) -> _RoomConnection:
        if role == "connector" and "connector" in self._connections:
            self._connections["connector"].is_authoritative = False
        connection = _RoomConnection(role=role, connection_id=connection_id)
        self._connections[role] = connection
        self._received.setdefault(connection_id, [])
        return connection

    def send_command(self, dashboard: _RoomConnection, command: dict[str, Any]) -> None:
        dashboard.assert_authoritative()
        connector = self._connections.get("connector")
        if connector is None or not connector.is_authoritative:
            raise ConnectorOfflineError("connector is offline")
        self._received[connector.connection_id].append(command)

    def received_commands(self, connector: _RoomConnection) -> list[dict[str, Any]]:
        return list(self._received.get(connector.connection_id, []))


class ReconnectBackoff:
    def __init__(self, base_seconds: int = 1, cap_seconds: int = 30, jitter_ratio: float = 0.2) -> None:
        self._base_seconds = base_seconds
        self._cap_seconds = cap_seconds
        self._jitter_ratio = jitter_ratio
        self._attempt = 0

    def next_delay(self) -> float:
        delay = min(self._cap_seconds, self._base_seconds * (2**self._attempt))
        self._attempt += 1
        if self._jitter_ratio == 0:
            return delay
        jitter = delay * self._jitter_ratio
        return max(0.0, delay + secrets.SystemRandom().uniform(-jitter, jitter))

    def reset(self) -> None:
        self._attempt = 0

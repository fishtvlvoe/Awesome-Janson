import unittest

from scripts.local_connector import ConnectorRuntimeError, LocalConnector, MemoryCredentialStore


class OfflineTransport:
    def request(self, *args, **kwargs):
        raise ConnectorRuntimeError("CLOUD_UNAVAILABLE")


class LocalConnectorRuntimeTests(unittest.TestCase):
    def test_local_cli_remains_usable_when_cloud_is_down(self) -> None:
        connector = LocalConnector(
            "https://offline.invalid",
            store=MemoryCredentialStore(),
            transport=OfflineTransport(),
        )

        result = connector.handle_command({
            "v": 1,
            "type": "command",
            "command_id": "local-1",
            "command": "connector.health",
            "payload": {},
        })

        self.assertEqual(result["status"], "completed")
        self.assertNotIn("hostname", result["payload"])
        self.assertNotIn("path", result["payload"])

    def test_pairing_uses_browser_callback_without_manual_token_input(self) -> None:
        opened = []

        class Transport:
            def __init__(self):
                self.calls = []

            def request(self, url, method="GET", body=None, headers=None):
                self.calls.append((url, method, body, headers))
                if url.endswith("/installations"):
                    return {
                        "installation_id": "ins_A",
                        "connector_credential": "ins_A.secret",
                        "dashboard_url": "https://dashboard.invalid/#/connect",
                    }
                return {
                    "ticket": "ins_A.ticket",
                    "dashboard_url": "https://dashboard.invalid/#/connect?ticket=ins_A.ticket",
                    "expires_in": 120,
                }

        connector = LocalConnector(
            "https://dashboard.invalid",
            store=MemoryCredentialStore(),
            transport=Transport(),
            opener=opened.append,
        )

        url = connector.pair()

        self.assertEqual(url, "https://dashboard.invalid/#/connect?ticket=ins_A.ticket")
        self.assertEqual(opened, [url])


if __name__ == "__main__":
    unittest.main()

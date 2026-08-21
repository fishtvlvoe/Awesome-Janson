import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hyperframes_renderkit_provider as provider  # noqa: E402


class HyperFramesRenderKitProviderTests(unittest.TestCase):
	def test_resolve_cli_uses_checkout_root_without_installing(self):
		with tempfile.TemporaryDirectory() as directory:
			cli = Path(directory) / "bin" / "hf-render"
			cli.parent.mkdir()
			cli.write_text("#!/bin/sh\n", encoding="utf-8")
			cli.chmod(0o755)
			self.assertEqual(provider.resolve_cli(root=Path(directory)), cli)

	def test_build_command_keeps_project_and_delivery_options_explicit(self):
		command = provider.build_command(
			Path("/opt/hf/bin/hf-render"),
			"plan",
			Path("/tmp/hyperframes-project"),
			Path("/tmp/delivery.json"),
			Path("/tmp/report"),
		)
		self.assertEqual(
			command,
			[
				"/opt/hf/bin/hf-render",
				"plan",
				"/tmp/hyperframes-project",
				"--config",
				"/tmp/delivery.json",
				"--report",
				"/tmp/report",
			],
		)

	def test_provider_stops_before_upstream_when_host_is_unsupported(self):
		with tempfile.TemporaryDirectory() as directory:
			with patch.object(provider, "host_supported", return_value=False), patch.object(provider.subprocess, "run") as run:
				result = provider.run_provider("check", Path(directory), cli=Path("/tmp/hf-render"))
		self.assertEqual(result, 2)
		run.assert_not_called()

	def test_dry_run_does_not_execute_upstream(self):
		with tempfile.TemporaryDirectory() as directory:
			cli = Path(directory) / "hf-render"
			cli.write_text("#!/bin/sh\n", encoding="utf-8")
			cli.chmod(0o755)
			with patch.object(provider, "host_supported", return_value=True), patch.object(provider.subprocess, "run") as run:
				result = provider.run_provider("check", Path(directory), cli=cli, dry_run=True)
		self.assertEqual(result, 0)
		run.assert_not_called()


if __name__ == "__main__":
	unittest.main()

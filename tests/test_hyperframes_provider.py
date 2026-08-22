import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import hyperframes_provider as provider  # noqa: E402


class HyperFramesProviderTests(unittest.TestCase):
	def test_build_command_supports_local_render_and_docker(self):
		command = provider.build_command(
			["npx", "hyperframes"],
			"render",
			output=Path("final.mp4"),
			composition=Path("compositions/hero.html"),
			docker=True,
		)
		self.assertEqual(
			command,
			["npx", "hyperframes", "render", "-c", "compositions/hero.html", "--output", "final.mp4", "--docker"],
		)

	def test_dry_run_does_not_execute_cli(self):
		with tempfile.TemporaryDirectory() as directory:
			project = Path(directory)
			with patch.object(provider.subprocess, "run") as run:
				result = provider.run_provider("render", project, cli=["npx", "hyperframes"], output=Path("out.mp4"), dry_run=True)
		self.assertEqual(result, 0)
		run.assert_not_called()

	def test_missing_project_stops_before_cli(self):
		with tempfile.TemporaryDirectory() as directory:
			missing = Path(directory) / "missing"
			with patch.object(provider.subprocess, "run") as run:
				result = provider.run_provider("lint", missing, cli=["hyperframes"])
		self.assertEqual(result, 2)
		run.assert_not_called()

	def test_init_allows_target_directory_to_be_created_by_cli(self):
		with tempfile.TemporaryDirectory() as directory:
			target = Path(directory) / "my-video"
			with patch.object(provider.subprocess, "run", return_value=type("Result", (), {"returncode": 0})()) as run:
				result = provider.run_provider("init", target, cli=["hyperframes"])
		self.assertEqual(result, 0)
		run.assert_called_once_with(["hyperframes", "init", "my-video"], cwd=Path(directory), check=False)


if __name__ == "__main__":
	unittest.main()

#!/usr/bin/env python3
"""Optional adapter for the local HyperFrames CLI.

HyperFrames is the local HTML-to-video route for Awesome-Janson.  This adapter
only assembles and delegates CLI commands; it does not replace the existing
FFmpeg pipeline or require a Linux host.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import Sequence


UPSTREAM_URL = "https://github.com/heygen-com/hyperframes"
ACTIONS = ("doctor", "init", "lint", "check", "preview", "render")


def resolve_cli(explicit: str | None = None) -> list[str] | None:
	"""Find a globally installed CLI, then fall back to the official npx entry."""
	if explicit:
		candidate = Path(explicit).expanduser()
		return [str(candidate)] if candidate.is_file() and os.access(candidate, os.X_OK) else None
	installed = shutil.which("hyperframes")
	if installed:
		return [installed]
	npx = shutil.which("npx")
	return [npx, "hyperframes"] if npx else None


def build_command(
	cli: Sequence[str],
	action: str,
	*,
	output: Path | None = None,
	composition: Path | None = None,
	example: str | None = None,
	docker: bool = False,
) -> list[str]:
	if action not in ACTIONS:
		raise ValueError(f"不支援的 HyperFrames 動作：{action}")
	command = [*cli, action]
	if composition:
		command.extend(["-c", str(composition)])
	if example:
		if action != "init":
			raise ValueError("--example 只能搭配 HyperFrames init")
		command.extend(["--example", example])
	if output:
		command.extend(["--output", str(output)])
	if docker:
		command.append("--docker")
	return command


def run_provider(
	action: str,
	project: Path,
	*,
	cli: Sequence[str] | None = None,
	output: Path | None = None,
	composition: Path | None = None,
	example: str | None = None,
	docker: bool = False,
	dry_run: bool = False,
) -> int:
	if action != "init" and not project.is_dir():
		print(f"❌ HyperFrames 專案不存在或不是資料夾：{project}")
		return 2
	resolved = list(cli) if cli else resolve_cli()
	if resolved is None:
		print("❌ 找不到 HyperFrames CLI，也找不到 npx。", flush=True)
		print(f"   官方來源：{UPSTREAM_URL}")
		return 2
	command = build_command(resolved, action, output=output, composition=composition, example=example, docker=docker)
	working_directory = project if project.is_dir() else project.parent
	if action == "init":
		command.append(project.name)
	print("$", " ".join(command), flush=True)
	if dry_run:
		return 0
	return subprocess.run(command, cwd=working_directory, check=False).returncode


def main() -> int:
	parser = argparse.ArgumentParser(description="剪神的 HyperFrames optional provider")
	parser.add_argument("action", choices=ACTIONS, help="交給 HyperFrames CLI 的動作")
	parser.add_argument("project", type=Path, help="HyperFrames 專案資料夾；init 時是目標資料夾")
	parser.add_argument("--cli", default=None, help="直接指定 hyperframes 可執行檔")
	parser.add_argument("--output", type=Path, default=None, help="輸出影片路徑")
	parser.add_argument("--composition", type=Path, default=None, help="指定 HTML composition")
	parser.add_argument("--example", default=None, help="init 時指定 HyperFrames 範例，例如 blank")
	parser.add_argument("--docker", action="store_true", help="使用 HyperFrames deterministic Docker route")
	parser.add_argument("--dry-run", action="store_true", help="只印出命令，不執行")
	args = parser.parse_args()
	return run_provider(
		args.action,
		args.project,
		cli=[args.cli] if args.cli else None,
		output=args.output,
		composition=args.composition,
		example=args.example,
		docker=args.docker,
		dry_run=args.dry_run,
	)


if __name__ == "__main__":
	raise SystemExit(main())

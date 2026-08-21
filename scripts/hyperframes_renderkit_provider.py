#!/usr/bin/env python3
"""Optional adapter for xiaotianfotos/HyperFrames-RenderKit.

The RenderKit runtime is intentionally not vendored.  This adapter only
validates the host/project boundary and delegates to the upstream ``hf-render``
fail-closed CLI.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


UPSTREAM_URL = "https://github.com/xiaotianfotos/HyperFrames-RenderKit"
SUPPORTED_HOST = "Linux x86_64"


def host_supported() -> bool:
	return sys.platform.startswith("linux") and platform.machine().lower() in {"x86_64", "amd64"}


def resolve_cli(explicit: str | None = None, root: Path | None = None) -> Path | None:
	"""Resolve the upstream CLI without downloading or installing anything."""
	if explicit:
		candidate = Path(explicit).expanduser()
		return candidate if candidate.is_file() and os.access(candidate, os.X_OK) else None

	if root:
		candidate = root.expanduser() / "bin" / "hf-render"
		if candidate.is_file() and os.access(candidate, os.X_OK):
			return candidate

	for name in ("hf-render", "HF_RENDER"):
		candidate = shutil.which(name)
		if candidate:
			return Path(candidate)
	return None


def build_command(
	cli: Path,
	action: str,
	project: Path,
	config: Path | None = None,
	report: Path | None = None,
) -> list[str]:
	if action not in {"check", "plan", "run"}:
		raise ValueError(f"不支援的 HyperFrames RenderKit 動作：{action}")
	command = [str(cli), action, str(project)]
	if config:
		command.extend(["--config", str(config)])
	if report:
		command.extend(["--report", str(report)])
	return command


def run_provider(
	action: str,
	project: Path,
	*,
	cli: Path | None = None,
	root: Path | None = None,
	config: Path | None = None,
	report: Path | None = None,
	dry_run: bool = False,
) -> int:
	if not host_supported():
		print(f"❌ HyperFrames RenderKit 只支援 {SUPPORTED_HOST}；目前主機：{platform.system()} {platform.machine()}", file=sys.stderr)
		return 2
	if not project.is_dir():
		print(f"❌ HyperFrames 專案不存在或不是資料夾：{project}", file=sys.stderr)
		return 2

	resolved = resolve_cli(str(cli) if cli else None, root)
	if resolved is None:
		print("❌ 找不到 hf-render。請設定 AWJ_HYPERFRAMES_RENDERKIT_ROOT 或 AWJ_HYPERFRAMES_RENDERKIT_CLI。", file=sys.stderr)
		print(f"   官方來源：{UPSTREAM_URL}", file=sys.stderr)
		return 2

	command = build_command(resolved, action, project, config, report)
	print("$", " ".join(command), flush=True)
	if dry_run:
		return 0
	return subprocess.run(command, check=False).returncode


def main() -> int:
	parser = argparse.ArgumentParser(description="剪神的 HyperFrames-RenderKit optional provider")
	parser.add_argument("action", choices=("check", "plan", "run"), help="交給 hf-render 的動作")
	parser.add_argument("project", type=Path, help="HyperFrames 專案資料夾")
	parser.add_argument("--root", type=Path, default=None, help="HyperFrames-RenderKit checkout 根目錄")
	parser.add_argument("--cli", type=Path, default=None, help="直接指定 bin/hf-render")
	parser.add_argument("--config", type=Path, default=None, help="RenderKit delivery config")
	parser.add_argument("--report", type=Path, default=None, help="RenderKit report output directory")
	parser.add_argument("--dry-run", action="store_true", help="只印出命令，不執行渲染")
	args = parser.parse_args()
	root = args.root or (Path(os.environ["AWJ_HYPERFRAMES_RENDERKIT_ROOT"]) if os.environ.get("AWJ_HYPERFRAMES_RENDERKIT_ROOT") else None)
	cli = args.cli or (Path(os.environ["AWJ_HYPERFRAMES_RENDERKIT_CLI"]) if os.environ.get("AWJ_HYPERFRAMES_RENDERKIT_CLI") else None)
	return run_provider(args.action, args.project, cli=cli, root=root, config=args.config, report=args.report, dry_run=args.dry_run)


if __name__ == "__main__":
	raise SystemExit(main())

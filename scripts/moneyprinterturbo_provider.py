#!/usr/bin/env python3
"""剪神的 MoneyPrinterTurbo optional topic-video provider adapter。

預設只輸出即將執行的命令；只有明確傳入 --run 才會安裝／啟動上游 provider。
它不讀取、不列印、不接收 API key 參數，憑證由 provider 的安全設定流程處理。
"""
from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVIDER_DIR = ROOT / "integrations" / "moneyprinterturbo"
HELPER = PROVIDER_DIR / "mpt_agent.py"


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--subject", required=True, help="主題或腳本生成目標")
	parser.add_argument("--root", type=Path, help="MPT 安裝目錄；不填使用上游預設值")
	parser.add_argument("--run", action="store_true", help="明確執行 provider（可能需要安裝 uv／下載 MPT）")
	args = parser.parse_args()
	command = [
		"uv",
		"run",
		"--no-project",
		"--python",
		"3.11",
		"python",
		"mpt_agent.py",
		"--subject",
		args.subject,
	]
	if args.root:
		command.extend(["--root", str(args.root.expanduser())])
	if not args.run:
		print("MoneyPrinterTurbo provider command:")
		print(shlex.join(command))
		print("加上 --run 才會真的執行；既有長錄影請不要走這條路由。")
		return
	if not HELPER.is_file():
		raise SystemExit(f"找不到 MPT helper：{HELPER}")
	subprocess.run(command, cwd=PROVIDER_DIR, check=True)


if __name__ == "__main__":
	main()

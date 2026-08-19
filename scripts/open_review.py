#!/usr/bin/env python3
"""開啟剪神文字剪輯審稿器；資料與影片由瀏覽器內的檔案選擇器載入。"""
from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--edit", type=Path, help="提示要載入的 semantic_edit.json 路徑")
	parser.add_argument("--video", type=Path, help="提示要載入的原始影片路徑")
	args = parser.parse_args()
	page = ROOT / "review" / "index.html"
	if not page.exists():
		raise SystemExit(f"找不到審稿器：{page}")
	webbrowser.open(page.as_uri())
	print(f"✅ 已開啟：{page}")
	print("   1. 點『載入語意 JSON』選擇譯神輸出的完整 semantic_edit.json")
	print("   2. 點『載入原始影片』選擇要預覽的 mp4/mov（可略過）")
	if args.edit:
		print(f"   建議載入 JSON：{args.edit.resolve()}")
	if args.video:
		print(f"   建議載入影片：{args.video.resolve()}")


if __name__ == "__main__":
	main()

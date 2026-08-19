#!/usr/bin/env python3
"""建立長片模式的保守版 EDL。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


CUTS = [
	(1800.46, 1831.15, "移除開啟聊天室的操作等待"),
	(2961.79, 2990.13, "移除第一次書寫練習的等待"),
	(3012.48, 3027.33, "移除書寫練習等待"),
	(6616.80, 6648.04, "移除行動計畫書寫等待"),
	(7419.33, 7433.74, "移除提問後等待回覆的空檔"),
	(7658.55, 7692.17, "移除五分鐘練習等待"),
	(7818.92, 7831.92, "移除練習等待"),
	(7899.25, 8003.97, "移除等待參與者完成練習"),
	(8006.09, 8026.70, "移除最後練習等待"),
]


def build(source: Path, output: Path, duration: float) -> None:
	ranges = []
	cursor = 0.0
	for start, end, reason in CUTS:
		if start > cursor:
			ranges.append(
				{
					"source": "PT工作坊",
					"start": round(cursor, 3),
					"end": round(start, 3),
					"beat": "講座內容",
					"reason": "保留完整教學脈絡",
				}
			)
		cursor = end
	if cursor < duration:
		ranges.append(
			{
				"source": "PT工作坊",
				"start": round(cursor, 3),
				"end": round(duration, 3),
				"beat": "講座內容",
				"reason": "保留完整教學脈絡",
			}
		)
	kept = sum(r["end"] - r["start"] for r in ranges)
	payload = {
		"version": 1,
		"mode": "full-length-master-clean-cut",
		"sources": {"PT工作坊": str(source)},
		"ranges": ranges,
		"cuts": [
			{"start": start, "end": end, "reason": reason}
			for start, end, reason in CUTS
		],
		"grade": "none",
		"total_duration_s": round(kept, 3),
		"source_duration_s": round(duration, 3),
	}
	output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(f"保留 {kept / 60:.1f} 分鐘；移除 {(duration - kept) / 60:.1f} 分鐘；{len(ranges)} 段")


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("source", type=Path)
	parser.add_argument("output", type=Path)
	parser.add_argument("--duration", type=float, required=True)
	args = parser.parse_args()
	build(args.source.resolve(), args.output.resolve(), args.duration)

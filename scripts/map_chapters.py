#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("edl", type=Path)
	parser.add_argument("source_chapters", type=Path)
	parser.add_argument("output", type=Path)
	args = parser.parse_args()
	edl = json.loads(args.edl.read_text(encoding="utf-8"))
	chapters = json.loads(args.source_chapters.read_text(encoding="utf-8"))
	mapped = []
	for chapter in chapters:
		source_start = float(chapter["source_start"])
		offset = 0.0
		found = False
		for item in edl["ranges"]:
			start = float(item["start"])
			end = float(item["end"])
			if start <= source_start < end:
				mapped.append({**chapter, "output_start": round(offset + source_start - start, 3)})
				found = True
				break
			offset += end - start
		if not found:
			print(f"warning: chapter {chapter['id']} is inside a removed range")
	args.output.write_text(json.dumps(mapped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(f"✅ 映射 {len(mapped)} 個章節")


if __name__ == "__main__":
	main()

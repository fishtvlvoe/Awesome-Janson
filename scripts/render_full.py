#!/usr/bin/env python3
"""把完整語意剪輯與既有等待剪輯合併，輸出自動精修長片。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from apply_review import normalise_subtitle_style
from render_semantic import (
	build_cues,
	build_intervals,
	build_ranges,
	frame_align_intervals,
	render_filtered,
	write_ass,
)


def merge_cuts(cuts: list[dict]) -> list[dict]:
	"""合併重疊剪除區間，保留所有原因與 word id。"""
	ordered = sorted(
		(
			{
				**cut,
				"start": float(cut["start"]),
				"end": float(cut["end"]),
				"word_ids": [str(item) for item in cut.get("word_ids", [])],
			}
			for cut in cuts
			if float(cut.get("end", 0.0)) > float(cut.get("start", 0.0))
		),
		key=lambda item: (item["start"], item["end"]),
	)
	merged: list[dict] = []
	for cut in ordered:
		if merged and cut["start"] <= merged[-1]["end"]:
			current = merged[-1]
			current["end"] = max(current["end"], cut["end"])
			current["word_ids"].extend(
				item for item in cut["word_ids"] if item not in current["word_ids"]
			)
			if cut.get("reason") and cut["reason"] not in current.get("reasons", []):
				current.setdefault("reasons", []).append(cut["reason"])
			current["text"] = f"{current.get('text', '')}{cut.get('text', '')}"
		else:
			merged.append(
				{
					**cut,
					"reasons": [cut["reason"]] if cut.get("reason") else [],
				}
			)
	for cut in merged:
		cut["reason"] = "; ".join(cut.pop("reasons", [])) or "自動精修"
		cut["start"] = round(cut["start"], 6)
		cut["end"] = round(cut["end"], 6)
	return merged


def load_base_cuts(path: Path) -> list[dict]:
	payload = json.loads(path.read_text(encoding="utf-8"))
	cuts = payload.get("cuts")
	if isinstance(cuts, list):
		return [dict(cut) for cut in cuts if isinstance(cut, dict)]
	ranges = payload.get("ranges", [])
	result: list[dict] = []
	previous_end: float | None = None
	for item in ranges:
		start = float(item["start"])
		end = float(item["end"])
		if previous_end is not None and start > previous_end:
			result.append({"start": previous_end, "end": start, "reason": "既有等待剪輯"})
		previous_end = end
	return result


def remap_chapters(path: Path, cuts: list[dict], source_end: float) -> list[dict]:
	from render_semantic import output_time

	chapters = json.loads(path.read_text(encoding="utf-8"))
	result: list[dict] = []
	for index, chapter in enumerate(chapters, start=1):
		source_start = float(chapter.get("source_start", chapter.get("output_start", 0.0)))
		if source_start >= source_end:
			continue
		result.append(
			{
				"id": int(chapter.get("id", index)),
				"source_start": round(source_start, 3),
				"title": str(chapter.get("title", "")),
				"output_start": round(output_time(source_start, 0.0, cuts), 3),
			}
		)
	return result


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("edit", type=Path)
	parser.add_argument("--source", type=Path, required=True)
	parser.add_argument("--base-edl", type=Path, required=True)
	parser.add_argument("--chapters", type=Path, required=True)
	parser.add_argument("--output-dir", type=Path, required=True)
	parser.add_argument("--render", action="store_true")
	parser.add_argument("--crf", default="23")
	parser.add_argument("--preset", default="veryfast")
	args = parser.parse_args()

	edit = json.loads(args.edit.read_text(encoding="utf-8"))
	args.output_dir.mkdir(parents=True, exist_ok=True)
	source_start = float(edit.get("source_start", 0.0))
	source_end = float(edit["source_end"])
	semantic_cuts = build_intervals(edit, physical_cut=True)
	base_cuts = load_base_cuts(args.base_edl)
	cuts = [
		cut
		for cut in merge_cuts(frame_align_intervals(base_cuts + semantic_cuts))
		if float(cut["end"]) > source_start and float(cut["start"]) < source_end
	]
	ranges = build_ranges(args.source.resolve(), source_start, source_end, cuts)
	chapters = remap_chapters(args.chapters, cuts, source_end)

	edl = {
		"version": 1,
		"mode": "full-length-auto-semantic-clean-cut",
		"sources": {"PT工作坊": str(args.source.resolve())},
		"ranges": ranges,
		"cuts": cuts,
		"source_start": source_start,
		"source_end": source_end,
		"total_duration_s": round(sum(item["end"] - item["start"] for item in ranges), 3),
	}
	edl_path = args.output_dir / "auto_master_edl.json"
	edl_path.write_text(json.dumps(edl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

	cues = build_cues(edit, source_start, cuts)
	cues_path = args.output_dir / "auto_master_cues.json"
	cues_path.write_text(json.dumps(cues, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	style = normalise_subtitle_style(edit.get("subtitle_style"))
	ass_path = args.output_dir / "auto_master_bilingual.ass"
	write_ass(
		cues,
		ass_path,
		zh_font_size=style["zh_font_size"],
		en_font_size=style["en_font_size"],
		show_english=style["show_english"],
	)
	chapters_path = args.output_dir / "auto_master_chapters.json"
	chapters_path.write_text(json.dumps(chapters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

	print(f"✅ EDL：{edl_path}")
	print(f"✅ 字幕：{ass_path}（{len(cues)} 條）")
	print(
		f"✅ 剪除：{len(cuts)} 段，共 "
		f"{sum(item['end'] - item['start'] for item in cuts):.2f} 秒；"
		f"輸出約 {edl['total_duration_s']:.2f} 秒"
	)
	if args.render:
		output = args.output_dir / "PT工作坊_auto_clean_bilingual.mp4"
		chapter_path = args.output_dir / "auto_master_chapter.txt"
		render_filtered(
			args.source.resolve(),
			output,
			source_start,
			source_end,
			cuts,
			ass_path,
			chapter_path,
			chapters[0]["title"] if chapters else "剪神自動精修",
			args.crf,
			args.preset,
			chapters=chapters,
		)
		print(f"✅ 成片：{output}")


if __name__ == "__main__":
	main()

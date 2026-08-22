#!/usr/bin/env python3
"""從完整語意 cue 以可重現規則挑選短影音候選片段。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def clean_text(value: object) -> str:
	return re.sub(r"\s+", "", str(value or ""))


def load_chapters(path: Path | None, source_end: float) -> list[dict]:
	if path and path.exists():
		return json.loads(path.read_text(encoding="utf-8"))
	return [{"id": 1, "source_start": 0.0, "title": "精華片段"}, {"id": 2, "source_start": source_end / 2, "title": "精華片段"}]


NATURAL_END_CHARS = set("。！？；.!?;")
TRAILING_CLOSING_CHARS = "」』）】〉》〕〗〙〛\"'”’)]}"
MAX_NATURAL_END_GAP_SECONDS = 0.9
EPSILON = 0.001


def extend_to_natural_end(
	chapter_cues: list[dict],
	start: float,
	end: float,
	maximum: float,
	limit_end: float | None = None,
) -> float:
	"""只在 cue 邊界收尾；逗號／冒號結尾會延伸到下一個完整句。"""
	ordered = sorted(chapter_cues, key=lambda cue: float(cue.get("source_start", 0.0)))
	allowed_end = min(start + maximum, limit_end) if limit_end is not None else start + maximum
	# 先將選段對齊到完整 cue。無法向前延伸時退回上一個 cue 邊界，不能切在說話中間。
	current_index = next(
		(index for index, cue in enumerate(ordered) if float(cue.get("source_start", 0.0)) < end - EPSILON <= float(cue.get("source_end", 0.0)) + EPSILON),
		None,
	)
	if current_index is None:
		# 目標點落在 ASR cue 間隙時，先回到前一個完整 cue，再依短暫停頓規則決定是否延伸。
		previous_indexes = [
			index
			for index, cue in enumerate(ordered)
			if float(cue.get("source_end", 0.0)) <= end + EPSILON
		]
		if not previous_indexes:
			return end
		current_index = previous_indexes[-1]
		end = float(ordered[current_index].get("source_end", end))
	current_end = float(ordered[current_index].get("source_end", end))
	if current_end > end + EPSILON:
		if current_end <= allowed_end + EPSILON:
			end = current_end
		else:
			previous_end = max(
				(float(cue.get("source_end", start)) for cue in ordered[:current_index] if float(cue.get("source_end", start)) <= end + EPSILON),
				default=start,
			)
			return previous_end
	while current_index < len(ordered) - 1:
		current_cue = ordered[current_index]
		tail = clean_text(current_cue.get("zh"))
		terminal_tail = tail.rstrip(TRAILING_CLOSING_CHARS)
		if terminal_tail and terminal_tail[-1] in NATURAL_END_CHARS:
			break
		next_cue = ordered[current_index + 1]
		current_end = float(current_cue.get("source_end", end))
		next_start = float(next_cue.get("source_start", current_end))
		# 不為補完整句保留長段靜音；短暫停頓仍可自然銜接。
		if next_start - current_end > MAX_NATURAL_END_GAP_SECONDS + EPSILON:
			break
		next_end = float(next_cue.get("source_end", end))
		if next_end > allowed_end + EPSILON:
			break
		end = next_end
		current_index += 1
	return end


def score_window(cues: list[dict], start: float, end: float) -> tuple[float, list[dict]]:
	inside = [
		cue
		for cue in cues
		if float(cue.get("source_end", 0.0)) > start and float(cue.get("source_start", 0.0)) < end
	]
	text = "".join(clean_text(cue.get("zh")) for cue in inside)
	keywords = ("客戶", "合作", "引薦", "Power Team", "成長", "業績", "方法", "做什麼", "成功")
	keyword_hits = sum(text.count(keyword) for keyword in keywords)
	meaningful = sum(1 for cue in inside if len(clean_text(cue.get("zh"))) >= 6)
	return len(text) + keyword_hits * 24 + meaningful * 3, inside


def build_candidates(edit: dict, chapters: list[dict], minimum: float, maximum: float) -> list[dict]:
	cues = sorted(edit.get("cues", []), key=lambda cue: float(cue.get("source_start", 0.0)))
	source_end = float(edit.get("source_end", 0.0))
	candidates: list[dict] = []
	for index, chapter in enumerate(chapters):
		chapter_start = float(chapter.get("source_start", 0.0))
		next_start = (
			float(chapters[index + 1].get("source_start"))
			if index + 1 < len(chapters)
			else source_end
		)
		chapter_end = min(source_end, max(chapter_start + minimum, next_start))
		chapter_cues = [cue for cue in cues if chapter_start <= float(cue.get("source_start", 0.0)) < chapter_end]
		if not chapter_cues:
			continue
		for start_cue in chapter_cues[:: max(1, len(chapter_cues) // 8)]:
			start = max(chapter_start, float(start_cue.get("source_start", chapter_start)))
			target_end = start + (minimum + maximum) / 2
			end_cue = next(
				(cue for cue in chapter_cues if float(cue.get("source_end", 0.0)) >= target_end),
				chapter_cues[-1],
			)
			end = min(chapter_end, float(end_cue.get("source_end", target_end)))
			if end - start < minimum:
				end = min(chapter_end, start + minimum)
			if end - start > maximum:
				end = start + maximum
			end = extend_to_natural_end(chapter_cues, start, end, maximum, limit_end=chapter_end)
			if end - start < minimum:
				continue
			score, inside = score_window(cues, start, end)
			candidates.append(
				{
					"source_start": round(start, 3),
					"source_end": round(end, 3),
					"title": str(chapter.get("title", "精華片段")),
					"chapter_id": chapter.get("id", index + 1),
					"score": round(score, 2),
					"cue_count": len(inside),
				}
			)
	return sorted(candidates, key=lambda item: (-item["score"], item["source_start"]))


def choose_non_overlapping(candidates: list[dict], count: int, separation: float) -> list[dict]:
	chosen: list[dict] = []
	for candidate in candidates:
		if any(
			candidate["source_start"] < item["source_end"] + separation
			and candidate["source_end"] > item["source_start"] - separation
			for item in chosen
		):
			continue
		chosen.append(candidate)
		if len(chosen) >= count:
			break
	return sorted(chosen, key=lambda item: item["source_start"])


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("edit", type=Path)
	parser.add_argument("output", type=Path)
	parser.add_argument("--chapters", type=Path)
	parser.add_argument("--count", type=int, default=3)
	parser.add_argument("--min-duration", type=float, default=45.0)
	parser.add_argument("--max-duration", type=float, default=75.0)
	args = parser.parse_args()
	edit = json.loads(args.edit.read_text(encoding="utf-8"))
	chapters = load_chapters(args.chapters, float(edit.get("source_end", 0.0)))
	candidates = build_candidates(edit, chapters, args.min_duration, args.max_duration)
	chosen = choose_non_overlapping(candidates, args.count, separation=30.0)
	if len(chosen) < args.count:
		raise SystemExit(f"只找到 {len(chosen)} 個不重疊片段，無法滿足 {args.count} 支短影音")
	for index, segment in enumerate(chosen, start=1):
		segment["id"] = index
		segment["output"] = f"short_{index:02d}.mp4"
	payload = {
		"schema_version": 1,
		"tool": "awesome-janson",
		"mode": "shorts-master-local-fallback",
		"source_edit": str(args.edit.resolve()),
		"segments": chosen,
		"candidates_considered": len(candidates),
	}
	args.output.parent.mkdir(parents=True, exist_ok=True)
	args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(f"✅ 挑選 {len(chosen)} 支短影音：{args.output}")
	for segment in chosen:
		print(
			f"   short_{segment['id']:02d}: {segment['source_start']:.1f}–{segment['source_end']:.1f}s "
			f"{segment['title']}（score {segment['score']:.0f}）"
		)


if __name__ == "__main__":
	main()

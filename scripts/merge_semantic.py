#!/usr/bin/env python3
"""合併多批譯神語意編輯結果，保留 word id 與時間順序。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("output", type=Path)
	parser.add_argument("inputs", type=Path, nargs="+")
	args = parser.parse_args()
	payloads = [json.loads(path.read_text(encoding="utf-8")) for path in args.inputs]
	payloads.sort(key=lambda item: float(item["source_start"]))
	words: list[dict] = []
	cues: list[dict] = []
	deletions: list[dict] = []
	seen_words: set[str] = set()
	for payload in payloads:
		for word in payload.get("words", []):
			if word["id"] in seen_words:
				continue
			seen_words.add(word["id"])
			words.append(word)
		cues.extend(payload.get("cues", []))
		deletions.extend(payload.get("deletions", []))
	words.sort(key=lambda item: (item["start"], item["end"], item["id"]))
	order = {word["id"]: index for index, word in enumerate(words)}
	cues.sort(key=lambda cue: min(order[item] for item in cue["word_ids"] if item in order))
	for cue_id, cue in enumerate(cues, start=1):
		cue["id"] = cue_id
		cue["word_ids"] = sorted(set(cue["word_ids"]), key=order.__getitem__)
		cue["drop_word_ids"] = sorted(set(cue.get("drop_word_ids", [])), key=order.__getitem__)
		cue["kept_word_ids"] = [item for item in cue["word_ids"] if item not in set(cue["drop_word_ids"])]
	deletions.sort(key=lambda item: (item["start"], item["end"]))
	merged = {
		"schema_version": 1,
		"tool": "awesome-janson",
		"language_editor": "awesome-eason",
		"mode": "semantic-subtitle-and-conservative-filler-edit",
		"source_start": min(float(item["source_start"]) for item in payloads),
		"source_end": max(float(item["source_end"]) for item in payloads),
		"batch_seconds": [item.get("batch_seconds") for item in payloads],
		"words": words,
		"cues": cues,
		"deletions": deletions,
		"repaired_word_ids": [word_id for item in payloads for word_id in item.get("repaired_word_ids", [])],
		"stats": {
			"word_count": len(words),
			"cue_count": len(cues),
			"deletion_count": len(deletions),
			"deleted_duration_s": round(sum(float(item["end"]) - float(item["start"]) for item in deletions), 3),
		},
	}
	args.output.parent.mkdir(parents=True, exist_ok=True)
	args.output.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(
		f"✅ 合併 {len(payloads)} 批：{len(cues)} cues、{len(deletions)} 個贅詞，"
		f"約 {merged['stats']['deleted_duration_s']:.2f} 秒"
	)


if __name__ == "__main__":
	main()

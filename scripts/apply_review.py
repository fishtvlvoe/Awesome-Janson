#!/usr/bin/env python3
"""把文字剪輯審稿結果套用到譯神語意編輯 JSON。"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


REVIEW_SCHEMA_VERSION = 1


def _as_id(value: Any) -> str:
	return str(value)


def _cue_id(cue: dict[str, Any]) -> str:
	return _as_id(cue.get("id", ""))


def _word_duration(word: dict[str, Any]) -> float:
	return max(0.0, float(word.get("end", 0.0)) - float(word.get("start", 0.0)))


def normalise_subtitle_style(style: Any) -> dict[str, Any]:
	style = style if isinstance(style, dict) else {}
	def number_in_range(value: Any, fallback: int, minimum: int, maximum: int) -> int:
		try:
			number = int(round(float(value)))
		except (TypeError, ValueError):
			return fallback
		return min(maximum, max(minimum, number))
	return {
		"zh_font_size": number_in_range(style.get("zh_font_size"), 50, 24, 64),
		"en_font_size": number_in_range(style.get("en_font_size"), 30, 14, 42),
		"show_english": style.get("show_english") is not False,
	}


def load_review_state(path: Path) -> dict[str, Any]:
	payload = json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(payload, dict):
		raise ValueError("審稿檔必須是 JSON 物件")
	# 允許直接把已套用的 edit JSON 再傳給 CLI。
	if isinstance(payload.get("review"), dict):
		return payload["review"]
	if payload.get("kind") != "awesome-janson-review":
		raise ValueError("審稿檔缺少 kind=awesome-janson-review")
	return payload


def apply_review(edit: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
	"""以人工核准結果建立可直接交給 render_semantic.py 的 edit payload。

	manual-review 模式採「未核准不剪」：原本由 AI 建議的贅詞不會因為載入審稿檔
	就自動被剪掉，只有 approved_word_ids / approved_cue_ids 會進入時間軸。
	"""
	result = copy.deepcopy(edit)
	if "subtitle_style" in review:
		result["subtitle_style"] = normalise_subtitle_style(review.get("subtitle_style"))
	words = [word for word in result.get("words", []) if isinstance(word, dict)]
	word_by_id = {_as_id(word.get("id")): word for word in words}
	cues = [cue for cue in result.get("cues", []) if isinstance(cue, dict)]
	cue_by_id = {_cue_id(cue): cue for cue in cues}

	requested_word_ids = [_as_id(item) for item in review.get("approved_word_ids", [])]
	requested_cue_ids = [_as_id(item) for item in review.get("approved_cue_ids", [])]
	unknown_words = [item for item in requested_word_ids if item not in word_by_id]
	unknown_cues = [item for item in requested_cue_ids if item not in cue_by_id]
	if unknown_words:
		raise ValueError("審稿檔含未知 word id：" + ", ".join(unknown_words[:10]))
	if unknown_cues:
		raise ValueError("審稿檔含未知 cue id：" + ", ".join(unknown_cues[:10]))

	approved_cue_ids = set(requested_cue_ids)
	approved_word_ids = set(requested_word_ids)
	# 整句刪除優先；同一句的單字核准不需要再重複切一次。
	for cue_id in approved_cue_ids:
		approved_word_ids.difference_update(
			_as_id(word_id) for word_id in cue_by_id[cue_id].get("word_ids", [])
		)

	decision_by_cue = {
		_as_id(key): str(value)
		for key, value in (review.get("decision_by_cue") or {}).items()
		if _as_id(key) in cue_by_id
	}
	for cue in cues:
		cue_id = _cue_id(cue)
		cue_word_ids = [_as_id(item) for item in cue.get("word_ids", []) if _as_id(item) in word_by_id]
		if cue_id in approved_cue_ids:
			deleted_ids = cue_word_ids
		else:
			deleted_ids = [word_id for word_id in cue_word_ids if word_id in approved_word_ids]
		cue["drop_word_ids"] = deleted_ids
		cue["kept_word_ids"] = [word_id for word_id in cue_word_ids if word_id not in set(deleted_ids)]

	deletions: list[dict[str, Any]] = []
	for word_id in sorted(approved_word_ids, key=lambda item: (float(word_by_id[item].get("start", 0)), item)):
		word = word_by_id[word_id]
		deletions.append(
			{
				"word_id": word_id,
				"start": word.get("start"),
				"end": word.get("end"),
				"text": word.get("text", ""),
				"reason": "manual-review",
				"confidence": 1.0,
			}
		)

	stored_review = {
		"schema_version": REVIEW_SCHEMA_VERSION,
		"mode": "manual-review",
		"subtitle_style": normalise_subtitle_style(review.get("subtitle_style", result.get("subtitle_style"))),
		"approved_word_ids": sorted(approved_word_ids, key=lambda item: (float(word_by_id[item].get("start", 0)), item)),
		"approved_cue_ids": sorted(approved_cue_ids, key=lambda item: (float(cue_by_id[item].get("source_start", 0)), item)),
		"decision_by_cue": decision_by_cue,
		"source_edit_schema_version": edit.get("schema_version"),
	}
	result["review"] = stored_review
	result["deletions"] = deletions
	result["stats"] = {
		**(result.get("stats") or {}),
		"word_count": len(words),
		"cue_count": len(cues),
		"deletion_count": len(deletions),
		"deleted_duration_s": round(sum(_word_duration(word_by_id[item]) for item in approved_word_ids), 3),
		"manual_deleted_cue_count": len(approved_cue_ids),
	}
	return result


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("edit", type=Path, help="譯神輸出的 semantic_edit.json")
	parser.add_argument("review", type=Path, help="review/index.html 匯出的審稿 JSON")
	parser.add_argument("output", type=Path, help="套用後的 reviewed_edit.json")
	args = parser.parse_args()

	edit = json.loads(args.edit.read_text(encoding="utf-8"))
	review = load_review_state(args.review)
	result = apply_review(edit, review)
	args.output.parent.mkdir(parents=True, exist_ok=True)
	args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(
		f"✅ 審稿結果已套用：{args.output}；"
		f"核准單字 {len(result['review']['approved_word_ids'])} 個、"
		f"整句 {len(result['review']['approved_cue_ids'])} 句"
	)


if __name__ == "__main__":
	main()

#!/usr/bin/env python3
"""用譯神規則把逐字稿整理成語意字幕與保守贅詞剪輯標記。"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-flash"
HARD_FILLERS = {"嗯", "呃", "欸", "哎", "喔", "哦", "啊", "哇", "ok"}
CONTEXT_FILLERS = {"這個", "那個", "就是", "就是說", "然後", "所以", "那", "來"}


def parse_json(text: str) -> Any:
	text = text.strip()
	text = re.sub(r"^```(?:json)?\s*", "", text)
	text = re.sub(r"\s*```$", "", text)
	return json.loads(text)


def load_words(path: Path, start: float, end: float) -> list[dict]:
	transcript = json.loads(path.read_text(encoding="utf-8"))
	words: list[dict] = []
	for segment in transcript:
		segment_id = segment.get("id", 0)
		for word_index, raw_word in enumerate(segment.get("words", [])):
			if raw_word.get("start") is None or raw_word.get("end") is None:
				continue
			word_start = float(raw_word["start"])
			word_end = float(raw_word["end"])
			# 以 token 起點分配批次；跨邊界的 token 由前一批負責，避免平行處理時重複。
			if word_start < start or word_start >= end:
				continue
			text = str(raw_word.get("word", "")).strip()
			if not text:
				continue
			words.append(
				{
					"id": f"{segment_id}:{word_index}",
					"segment_id": segment_id,
					"word_index": word_index,
					"text": text,
					"start": round(max(start, word_start), 3),
					"end": round(min(end, word_end), 3),
					"probability": raw_word.get("probability"),
				}
			)
	words.sort(key=lambda item: (item["start"], item["end"], item["id"]))
	return words


def make_prompt(words: list[dict], start: float, end: float, shorts: bool = False) -> str:
	word_rows = [
		{
			"id": word["id"],
			"t": [word["start"], word["end"]],
			"raw": word["text"],
		}
		for word in words
	]
	en_example = '""' if shorts else '"Natural English"'
	short_rules = (
		"【短影音專用規則】\n"
		"- 受眾是台灣中文市場；en 欄位一律輸出空字串，不要翻譯英文字幕。\n"
		"- 每個 cue 必須是一個完整口語意群，字幕時間必須涵蓋整個意群；禁止讓畫面只剩一個字、單一標點或句尾孤兒。\n"
		"- 如果原始 word token 被 ASR 或前一個 cue 切碎，請合併到相鄰 cue；不要在詞中間切畫面，也不要為了湊節奏把一句話拆成單字。\n"
		"- 短字幕寧可維持完整一句並少一個 cue，也不要產生『麼？』『。』『到。』這種孤立片段。\n"
	) if shorts else ""
	return (
		"你是『譯神 / Awesome-Eason』，負責替『剪神 / Awesome-Janson』做語言編輯。\n"
		"這是一段台灣繁體中文工作坊影片的 faster-whisper 原始逐字稿。\n"
		"請依照語意重新分句、修正明顯 ASR 錯字、標記可以從聲音與畫面一起剪掉的贅詞。\n\n"
		"【重要分工】\n"
		"- 剪神會依照 word id 的時間碼真的剪影片，所以不能憑空改時間。\n"
		"- 每個輸入 word id 必須且只能出現在一個 cue 的 word_ids 裡。\n"
		"- 如果某個詞要刪除，仍然放在該 cue 的 word_ids，並放進該 cue 的 drop_word_ids。\n"
		"- 不確定的詞一律保留，不要為了讓文字漂亮而剪掉內容。\n\n"
		"【贅詞規則（保守模式）】\n"
		"- 第一版只能把獨立的『嗯、呃、欸、哎、喔、哦、啊、哇、OK』標記為 drop；詞若貼著句子，就算是語氣詞也先保留。\n"
		"- 『好』只有在 cue 幾乎只有這個字、且明顯是空回應時才標記。\n"
		"- 『這個、那個、就是、然後、所以、那、來』是第二級候選，只有你非常確定是口頭填充時才標記，並給 confidence >= 0.85。\n"
		"- 不可刪除任何其他詞來修正 ASR；『客戶、無線、廠商、成長、業績』等內容詞一律保留。\n"
		"- 不可無腦刪除『這個客戶、那個方案、然後我們進入下一階段』中的有意義用法。\n"
		"- 明顯重複或說到一半重來的殘句先保留，除非能精準指出重複的安全 filler token。\n"
		"- 專有名詞、人名、品牌、BNI、Power Team、PT、Wi-Fi、AI、CRM、VCP、MSP 等要保留並修正大小寫。\n\n"
		"【分句規則】\n"
		"- 一個 cue 表達一個完整語意，但必須有硬上限：中文每行最多 22 個視覺字元，英文每行最多 60 個字元；超過就依逗號、頓號、連接詞或自然停頓拆成多個 cue。\n"
		"- 不拆開主詞與動詞、名詞片語、專有名詞或因果關係；寧可多一個 cue，也不要塞成超長句。\n"
		"- 中文主字幕最多兩行；英文是自然口語翻譯，不要逐字硬翻，也最多兩行。\n"
		"- cue 通常約 1.5～5.5 秒；完整短句可較短，不能為了湊秒數合併不同意思。\n"
		"- 盡量涵蓋全部 word id；純空白不在輸入中，不需要補。\n\n"
		+ short_rules
		+ "【輸出格式】只回傳 JSON，不要 Markdown：\n"
		"{\n"
		'  "cues": [\n'
		f'    {{"word_ids":["0:0"],"drop_word_ids":[],"zh":"整理後的繁中","en":{en_example},"confidence":0.0}}\n'
		"  ]\n"
		"}\n\n"
		f"這批素材的來源範圍是 {start:.3f}～{end:.3f} 秒。輸入 word tokens：\n"
		+ json.dumps(word_rows, ensure_ascii=False, separators=(",", ":"))
	)


def call_gemini(words: list[dict], start: float, end: float, api_key: str, model: str, shorts: bool = False) -> dict:
	payload = {
		"contents": [{"role": "user", "parts": [{"text": make_prompt(words, start, end, shorts=shorts)}]}],
		"generationConfig": {
			"temperature": 0.1,
			"responseMimeType": "application/json",
		},
	}
	url = f"{API_BASE}/{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(api_key)}"
	request = urllib.request.Request(
		url,
		data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
		headers={"Content-Type": "application/json"},
		method="POST",
	)
	last_error: Exception | None = None
	for attempt in range(4):
		try:
			with urllib.request.urlopen(request, timeout=180) as response:
				body = json.loads(response.read().decode("utf-8"))
			text = body["candidates"][0]["content"]["parts"][0]["text"]
			result = parse_json(text)
			if not isinstance(result, dict) or not isinstance(result.get("cues"), list):
				raise ValueError("Gemini 回傳缺少 cues 陣列")
			return result
		except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError, json.JSONDecodeError) as error:
			last_error = error
			if attempt < 3:
				time.sleep(2**attempt)
	if last_error is not None:
		raise RuntimeError(f"語意編輯請求失敗：{last_error}") from last_error
	raise RuntimeError("語意編輯請求失敗")


def is_isolated(word_id: str, ids: list[str], known: dict[str, dict], order: dict[str, int]) -> bool:
	position = order[word_id]
	neighbour_ids = [item for item in ids if item != word_id]
	if not neighbour_ids:
		return True
	previous = [item for item in neighbour_ids if order[item] < position]
	next_items = [item for item in neighbour_ids if order[item] > position]
	gaps: list[float] = []
	if previous:
		word = known[previous[-1]]
		current = known[word_id]
		gaps.append(float(current["start"]) - float(word["end"]))
	if next_items:
		word = known[next_items[0]]
		current = known[word_id]
		gaps.append(float(word["start"]) - float(current["end"]))
	return any(gap >= 0.18 for gap in gaps)


def validate_and_normalise(result: dict, words: list[dict], start: float, end: float) -> dict:
	known = {word["id"]: word for word in words}
	order = {word["id"]: index for index, word in enumerate(words)}
	seen: set[str] = set()
	cues: list[dict] = []
	for cue_index, raw_cue in enumerate(result["cues"], start=1):
		if not isinstance(raw_cue, dict):
			continue
		ids: list[str] = []
		duplicate_ids: list[str] = []
		for item in raw_cue.get("word_ids", []):
			word_id = str(item)
			if word_id not in known:
				continue
			if word_id in seen or word_id in ids:
				duplicate_ids.append(word_id)
				continue
			ids.append(word_id)
		if not ids:
			continue
		seen.update(ids)
		confidence = float(raw_cue.get("confidence", 0.0) or 0.0)
		candidate_drop_ids = [str(item) for item in raw_cue.get("drop_word_ids", []) if str(item) in ids]
		drop_ids: list[str] = []
		for word_id in candidate_drop_ids:
			text = str(known[word_id]["text"]).strip().lower()
			isolated = is_isolated(word_id, ids, known, order)
			if text in HARD_FILLERS and isolated:
				drop_ids.append(word_id)
			elif text == "好" and isolated:
				drop_ids.append(word_id)
			elif text in CONTEXT_FILLERS and confidence >= 0.85:
				drop_ids.append(word_id)
		kept_ids = [item for item in ids if item not in set(drop_ids)]
		cues.append(
			{
				"id": cue_index,
				"word_ids": ids,
				"drop_word_ids": drop_ids,
				"kept_word_ids": kept_ids,
				"zh": str(raw_cue.get("zh", "")).strip(),
				"en": str(raw_cue.get("en", "")).strip(),
				"confidence": confidence,
				"duplicate_word_ids": duplicate_ids,
			}
		)
	missing = [word["id"] for word in words if word["id"] not in seen]
	repaired: list[str] = []
	if len(missing) > 20:
		raise ValueError(
			"Gemini 沒有覆蓋太多 word id；前 20 個未處理：" + ", ".join(missing[:20])
		)
	if missing:
		# 模型偶爾會漏掉 cue 尾端的一個字；小量漏字可掛回最近 cue，避免時間軸失去聲音。
		for word_id in missing:
			position = order[word_id]
			target = min(
				cues,
				key=lambda cue: min(abs(order[item] - position) for item in cue["word_ids"]),
			)
			target["word_ids"].append(word_id)
			seen.add(word_id)
			repaired.append(word_id)
	for cue in cues:
		cue["word_ids"].sort(key=lambda item: order[item])
		cue["drop_word_ids"].sort(key=lambda item: order[item])
		cue["kept_word_ids"] = [item for item in cue["word_ids"] if item not in set(cue["drop_word_ids"])]
		all_words = [known[item] for item in cue["word_ids"]]
		kept_words = [known[item] for item in cue["kept_word_ids"]]
		cue["source_start"] = round(all_words[0]["start"], 3)
		cue["source_end"] = round(all_words[-1]["end"], 3)
		if kept_words:
			cue["kept_source_start"] = round(kept_words[0]["start"], 3)
			cue["kept_source_end"] = round(kept_words[-1]["end"], 3)
		else:
			cue["kept_source_start"] = None
			cue["kept_source_end"] = None
	deletions: list[dict] = []
	for cue in cues:
		for word_id in cue["drop_word_ids"]:
			word = known[word_id]
			deletions.append(
				{
					"word_id": word_id,
					"start": word["start"],
					"end": word["end"],
					"text": word["text"],
					"reason": "filler-or-false-start",
					"confidence": cue["confidence"],
				}
			)
	deletions.sort(key=lambda item: item["start"])
	return {
		"schema_version": 1,
		"tool": "awesome-janson",
		"language_editor": "awesome-eason",
		"mode": "semantic-subtitle-and-conservative-filler-edit",
		"source_start": round(start, 3),
		"source_end": round(end, 3),
		"words": words,
		"cues": cues,
		"deletions": deletions,
		"repaired_word_ids": repaired,
		"stats": {
			"word_count": len(words),
			"cue_count": len(cues),
			"deletion_count": len(deletions),
			"deleted_duration_s": round(sum(item["end"] - item["start"] for item in deletions), 3),
		},
	}


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("transcript", type=Path)
	parser.add_argument("output", type=Path)
	parser.add_argument("--start", type=float, default=0.0)
	parser.add_argument("--end", type=float, default=600.0)
	parser.add_argument("--batch-seconds", type=float, default=300.0)
	parser.add_argument("--model", default=DEFAULT_MODEL)
	parser.add_argument("--raw-response", type=Path)
	parser.add_argument("--shorts", action="store_true", help="使用中文短影音字幕規則，不產生英文翻譯")
	args = parser.parse_args()
	api_key = os.environ.get("GEMINI_API_KEY")
	if not api_key:
		raise SystemExit("GEMINI_API_KEY is not set")
	if args.end <= args.start:
		raise SystemExit("--end 必須大於 --start")
	if args.batch_seconds <= 0:
		raise SystemExit("--batch-seconds 必須大於 0")
	words = load_words(args.transcript, args.start, args.end)
	if not words:
		raise SystemExit("指定範圍沒有 word timestamps")
	print(
		f"🧠 譯神整理 {args.start:.1f}–{args.end:.1f} 秒，共 {len(words)} 個 word tokens；"
		f"每批 {args.batch_seconds:.0f} 秒",
		flush=True,
	)
	raw_batches: list[dict] = []
	if args.raw_response and args.raw_response.exists():
		try:
			existing = json.loads(args.raw_response.read_text(encoding="utf-8"))
			raw_batches = [item for item in existing.get("batches", []) if isinstance(item, dict)]
		except (OSError, json.JSONDecodeError):
			raw_batches = []
	completed_batches = {round(float(item.get("start", -1.0)), 3): item for item in raw_batches}
	all_cues: list[dict] = []
	all_deletions: list[dict] = []
	cursor = args.start
	batch_number = 0
	while cursor < args.end:
		batch_number += 1
		batch_end = min(args.end, cursor + args.batch_seconds)
		batch_words = [word for word in words if cursor <= word["start"] < batch_end]
		if not batch_words:
			cursor = batch_end
			continue
		print(
			f"   批次 {batch_number}: {batch_words[0]['start']:.1f}–{batch_words[-1]['end']:.1f} 秒，"
			f"{len(batch_words)} words",
			flush=True,
		)
		cached = completed_batches.get(round(cursor, 3))
		if cached and isinstance(cached.get("result"), dict):
			print("      ♻️ 重用已完成的 API 回應", flush=True)
			result = cached["result"]
		else:
			result = call_gemini(batch_words, cursor, batch_end, api_key, args.model, shorts=args.shorts)
			raw_batches.append({"start": cursor, "end": batch_end, "result": result})
		if args.raw_response and not cached:
			args.raw_response.parent.mkdir(parents=True, exist_ok=True)
			args.raw_response.write_text(
				json.dumps({"batches": raw_batches}, ensure_ascii=False, indent=2) + "\n",
				encoding="utf-8",
			)
		try:
			batch_payload = validate_and_normalise(result, batch_words, cursor, batch_end)
		except ValueError as error:
			if args.raw_response:
				print(f"⚠️ 原始回應已保留：{args.raw_response}", flush=True)
			raise SystemExit(str(error)) from error
		all_cues.extend(batch_payload["cues"])
		all_deletions.extend(batch_payload["deletions"])
		cursor = batch_end
	for index, cue in enumerate(all_cues, start=1):
		cue["id"] = index
	all_deletions.sort(key=lambda item: item["start"])
	payload = {
		"schema_version": 1,
		"tool": "awesome-janson",
		"language_editor": "awesome-eason",
		"mode": "semantic-subtitle-and-conservative-filler-edit",
		"source_start": round(args.start, 3),
		"source_end": round(args.end, 3),
		"batch_seconds": args.batch_seconds,
		"words": words,
		"cues": all_cues,
		"deletions": all_deletions,
		"stats": {
			"word_count": len(words),
			"cue_count": len(all_cues),
			"deletion_count": len(all_deletions),
			"deleted_duration_s": round(sum(item["end"] - item["start"] for item in all_deletions), 3),
		},
	}
	args.output.parent.mkdir(parents=True, exist_ok=True)
	args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(
		f"✅ 產生 {payload['stats']['cue_count']} 個語意 cue；"
		f"標記 {payload['stats']['deletion_count']} 個贅詞，"
		f"約 {payload['stats']['deleted_duration_s']:.2f} 秒",
		flush=True,
	)


if __name__ == "__main__":
	main()

#!/usr/bin/env python3
"""把字詞時間軸映射到 EDL 輸出時間軸，建立可燒錄的 ASS 字幕。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from subtitle_layout import (
	ASS_FONT_NAME,
	EN_FONT_SIZE,
	ZH_FONT_SIZE,
	split_subtitle_cue,
	wrap_chinese,
	wrap_english,
)


def ass_time(seconds: float) -> str:
	cs = int(round(seconds * 100))
	h, cs = divmod(cs, 360000)
	m, cs = divmod(cs, 6000)
	s, cs = divmod(cs, 100)
	return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def clean(text: str) -> str:
	return re.sub(r"\s+", "", text).strip()


def make_cues(transcript: list[dict], edl: dict) -> list[dict]:
	words = []
	for segment in transcript:
		for word in segment.get("words", []):
			text = clean(word.get("word", ""))
			if not text or word.get("start") is None or word.get("end") is None:
				continue
			words.append({"text": text, "start": float(word["start"]), "end": float(word["end"])})
	words.sort(key=lambda item: item["start"])
	cues: list[dict] = []
	output_offset = 0.0
	for item in edl["ranges"]:
		start = float(item["start"])
		end = float(item["end"])
		inside = [word for word in words if word["end"] > start and word["start"] < end]
		current: list[dict] = []
		for word in inside:
			word_start = max(start, word["start"])
			word_end = min(end, word["end"])
			if not current:
				current = [{**word, "start": word_start, "end": word_end}]
				continue
			gap = word_start - current[-1]["end"]
			text_len = sum(len(part["text"]) for part in current)
			should_break = gap >= 0.55 or text_len >= 18 or word_end - current[0]["start"] >= 3.6
			if should_break:
				cues.append(_cue(current, output_offset, start))
				current = [{**word, "start": word_start, "end": word_end}]
			else:
				current.append({**word, "start": word_start, "end": word_end})
		if current:
			cues.append(_cue(current, output_offset, start))
		output_offset += end - start
	return cues


def _cue(words: list[dict], output_offset: float, source_start: float) -> dict:
	text = "".join(word["text"] for word in words)
	return {
		"id": 0,
		"source_start": round(words[0]["start"], 3),
		"source_end": round(words[-1]["end"], 3),
		"start": round(output_offset + words[0]["start"] - source_start, 3),
		"end": round(output_offset + words[-1]["end"] - source_start, 3),
		"zh": text,
	}


def write_ass(cues: list[dict], output: Path, translations: dict[str, str] | None = None) -> None:
	lines = [
		"[Script Info]",
		"ScriptType: v4.00+",
		"PlayResX: 1280",
		"PlayResY: 720",
		"ScaledBorderAndShadow: yes",
		"WrapStyle: 2",
		"",
		"[V4+ Styles]",
		"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
		f"Style: Default,{ASS_FONT_NAME},{ZH_FONT_SIZE},&H00FFFFFF,&H00FFFFFF,&H00101010,&HAA606060,0,0,0,0,100,100,0,0,3,8,2,2,60,60,32,1",
		"",
		"[Events]",
		"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
	]
	translations = translations or {}
	prepared: list[dict] = []
	for cue in cues:
		prepared.extend(
			split_subtitle_cue(
				{**cue, "en": translations.get(str(cue["id"]), "")}
			)
		)
	for cue in prepared:
		zh = wrap_chinese(cue["zh"]).replace("{", "\\{").replace("}", "\\}")
		en = wrap_english(cue.get("en", "")).replace("{", "\\{").replace("}", "\\}")
		text = f"{{\\fn{ASS_FONT_NAME}\\fs{ZH_FONT_SIZE}\\bord8\\shad2\\c&H00FFFFFF&\\4c&HAA606060&}}{zh}"
		if en:
			text += f"\\N{{\\fn{ASS_FONT_NAME}\\fs{EN_FONT_SIZE}\\bord8\\shad2\\c&H00E0E0E0&\\4c&HAA606060&}}{en}"
		lines.append(f"Dialogue: 0,{ass_time(cue['start'])},{ass_time(cue['end'])},Default,,0,0,0,,{text}")
	output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("transcript", type=Path)
	parser.add_argument("edl", type=Path)
	parser.add_argument("cues", type=Path)
	parser.add_argument("ass", type=Path)
	parser.add_argument("--translations", type=Path)
	args = parser.parse_args()
	transcript = json.loads(args.transcript.read_text(encoding="utf-8"))
	edl = json.loads(args.edl.read_text(encoding="utf-8"))
	cues = make_cues(transcript, edl)
	for index, cue in enumerate(cues, start=1):
		cue["id"] = index
	args.cues.write_text(json.dumps(cues, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	translations = json.loads(args.translations.read_text(encoding="utf-8")) if args.translations else {}
	write_ass(cues, args.ass, translations)
	print(f"✅ 產生 {len(cues)} 條繁中字幕：{args.ass}")


if __name__ == "__main__":
	main()

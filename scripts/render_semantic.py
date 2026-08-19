#!/usr/bin/env python3
"""把譯神語意編輯結果轉成剪輯 EDL、ASS，並可渲染測試片段。"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from apply_review import normalise_subtitle_style
from subtitle_layout import (
	ASS_FONT_NAME,
	EN_FONT_SIZE,
	ZH_FONT_SIZE,
	resolve_font_path,
	resolve_fonts_dir,
	wrap_chinese,
	wrap_english,
	split_subtitle_cue,
)


def ass_time(seconds: float) -> str:
	centiseconds = int(round(max(0.0, seconds) * 100))
	hours, centiseconds = divmod(centiseconds, 360000)
	minutes, centiseconds = divmod(centiseconds, 6000)
	seconds, centiseconds = divmod(centiseconds, 100)
	return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def escape_ass(text: str) -> str:
	# 保留 ASS 的 \\N 換行控制碼，只跳脫文字中的大括號。
	return text.replace("{", "\\{").replace("}", "\\}")


def build_intervals(edit: dict, physical_cut: bool) -> list[dict]:
	if not physical_cut:
		return []
	words = {str(word["id"]): word for word in edit["words"]}
	intervals: list[dict] = []
	review = edit.get("review") if isinstance(edit.get("review"), dict) else None
	if review and review.get("mode") == "manual-review":
		# 審稿模式採「未核准不剪」，避免把 AI 建議直接當成不可逆剪輯。
		approved_word_ids = {str(item) for item in review.get("approved_word_ids", [])}
		approved_cue_ids = {str(item) for item in review.get("approved_cue_ids", [])}
		for word_id in sorted(approved_word_ids, key=lambda item: float(words[item]["start"]) if item in words else float("inf")):
			if word_id not in words:
				continue
			word = words[word_id]
			intervals.append(
				{
					"start": float(word["start"]),
					"end": float(word["end"]),
					"word_id": word_id,
					"text": word.get("text", ""),
					"reason": "manual-review",
					"confidence": 1.0,
				}
			)
		for cue in edit.get("cues", []):
			if str(cue.get("id")) not in approved_cue_ids:
				continue
			start = cue.get("source_start")
			end = cue.get("source_end")
			if start is None or end is None or float(end) <= float(start):
				continue
			intervals.append(
				{
					"start": float(start),
					"end": float(end),
					"word_ids": [str(item) for item in cue.get("word_ids", [])],
					"text": str(cue.get("zh", "")),
					"reason": "manual-review-sentence",
					"confidence": 1.0,
				}
			)
	else:
		for deletion in edit.get("deletions", []):
			word_id = str(deletion["word_id"])
			if word_id not in words:
				continue
			word = words[word_id]
			intervals.append(
				{
					"start": float(word["start"]),
					"end": float(word["end"]),
					"word_id": word_id,
					"text": word["text"],
					"reason": deletion.get("reason", "filler-or-false-start"),
					"confidence": deletion.get("confidence", 0.0),
				}
			)
	intervals.sort(key=lambda item: (item["start"], item["end"]))
	merged: list[dict] = []
	for interval in intervals:
		word_ids = interval.get("word_ids") or [interval.get("word_id")]
		word_ids = [str(item) for item in word_ids if item]
		if merged and interval["start"] <= merged[-1]["end"]:
			merged[-1]["end"] = max(merged[-1]["end"], interval["end"])
			merged[-1]["word_ids"].extend(item for item in word_ids if item not in merged[-1]["word_ids"])
			merged[-1]["text"] += interval.get("text", "")
		else:
			merged.append(
				{
					"start": interval["start"],
					"end": interval["end"],
					"word_ids": word_ids,
					"text": interval.get("text", ""),
					"reason": interval["reason"],
					"confidence": interval["confidence"],
				}
			)
	return merged


def frame_align_intervals(cuts: list[dict], fps: int = 30) -> list[dict]:
	"""把語音刪除區間對齊 CFR 影格，讓音訊與畫面共用同一個刪除長度。"""
	aligned: list[dict] = []
	for cut in cuts:
		start = (int(float(cut["start"]) * fps + 0.999999) / fps)
		end = (int(float(cut["end"]) * fps + 0.000001) + 1) / fps
		if end <= start:
			continue
		aligned.append(
			{
				**cut,
				"start": round(start, 6),
				"end": round(end, 6),
				"frame_aligned": True,
				"word_ids": [str(item) for item in cut.get("word_ids", [])],
				"text": str(cut.get("text", "")),
			}
		)
	aligned.sort(key=lambda item: (item["start"], item["end"]))
	merged: list[dict] = []
	for cut in aligned:
		if merged and cut["start"] <= merged[-1]["end"]:
			merged[-1]["end"] = max(merged[-1]["end"], cut["end"])
			merged[-1]["word_ids"].extend(cut.get("word_ids", []))
			merged[-1]["text"] += cut.get("text", "")
		else:
			merged.append(cut)
	return merged


def build_ranges(source: Path, start: float, end: float, cuts: list[dict]) -> list[dict]:
	ranges: list[dict] = []
	cursor = start
	for cut in cuts:
		cut_start = max(start, float(cut["start"]))
		cut_end = min(end, float(cut["end"]))
		if cut_end <= cursor:
			continue
		if cut_start > cursor:
			ranges.append(
				{
					"source": "sample",
					"start": round(cursor, 3),
					"end": round(cut_start, 3),
					"beat": "語意剪輯測試",
					"reason": "保留語意內容",
				}
			)
		cursor = max(cursor, cut_end)
	if cursor < end:
		ranges.append(
			{
				"source": "sample",
				"start": round(cursor, 3),
				"end": round(end, 3),
				"beat": "語意剪輯測試",
				"reason": "保留語意內容",
			}
		)
	return ranges


def output_time(source_time: float, source_start: float, cuts: list[dict]) -> float:
	removed = 0.0
	for cut in cuts:
		if source_time <= cut["start"]:
			break
		removed += max(0.0, min(source_time, cut["end"]) - cut["start"])
	return max(0.0, source_time - source_start - removed)


def build_cues(edit: dict, source_start: float, cuts: list[dict]) -> list[dict]:
	words = {str(word["id"]): word for word in edit["words"]}
	review = edit.get("review") if isinstance(edit.get("review"), dict) else None
	if review and review.get("mode") == "manual-review":
		deleted_word_ids = {str(item) for item in review.get("approved_word_ids", [])}
		deleted_cue_ids = {str(item) for item in review.get("approved_cue_ids", [])}
	else:
		deleted_word_ids = {str(item["word_id"]) for item in edit.get("deletions", [])}
		deleted_cue_ids = set()
	result: list[dict] = []
	for index, cue in enumerate(edit["cues"], start=1):
		if str(cue.get("id", index)) in deleted_cue_ids:
			continue
		kept_ids = [str(word_id) for word_id in cue.get("word_ids", []) if str(word_id) not in deleted_word_ids]
		kept_words = [words[word_id] for word_id in kept_ids if word_id in words]
		if not kept_words or not cue.get("zh"):
			continue
		start = output_time(float(kept_words[0]["start"]), source_start, cuts)
		end = output_time(float(kept_words[-1]["end"]), source_start, cuts)
		if end <= start:
			continue
		result.append(
			{
				"id": index,
				"source_start": round(float(kept_words[0]["start"]), 3),
				"source_end": round(float(kept_words[-1]["end"]), 3),
				"start": round(start, 3),
				"end": round(end, 3),
				"zh": cue["zh"],
				"en": cue.get("en", ""),
				"drop_word_ids": [item for item in cue.get("drop_word_ids", []) if str(item) in deleted_word_ids],
				"confidence": cue.get("confidence", 0.0),
			}
		)
	split_result: list[dict] = []
	for cue in result:
		split_result.extend(split_subtitle_cue(cue))
	for cue_id, cue in enumerate(split_result, start=1):
		cue["id"] = cue_id
	return split_result


def write_ass(
	cues: list[dict],
	output: Path,
	zh_font_size: int = ZH_FONT_SIZE,
	en_font_size: int = EN_FONT_SIZE,
	show_english: bool = True,
) -> None:
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
		f"Style: Default,{ASS_FONT_NAME},{zh_font_size},&H00FFFFFF,&H00FFFFFF,&H00101010,&HAA606060,0,0,0,0,100,100,0,0,3,8,2,2,60,60,32,1",
		"",
		"[Events]",
		"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
	]
	for cue in cues:
		zh = escape_ass(wrap_chinese(cue["zh"]))
		en = escape_ass(wrap_english(cue.get("en", "")))
		text = f"{{\\fn{ASS_FONT_NAME}\\fs{zh_font_size}\\bord8\\shad2\\c&H00FFFFFF&\\4c&HAA606060&}}{zh}"
		if en and show_english:
			text += f"\\N{{\\fn{ASS_FONT_NAME}\\fs{en_font_size}\\bord8\\shad2\\c&H00E0E0E0&\\4c&HAA606060&}}{en}"
		lines.append(
			f"Dialogue: 0,{ass_time(cue['start'])},{ass_time(cue['end'])},Default,,0,0,0,,{text}"
		)
	output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def escape_filter_path(path: Path) -> str:
	return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def render_filtered(
	source: Path,
	output: Path,
	source_start: float,
	source_end: float,
	cuts: list[dict],
	ass_path: Path,
	chapter_path: Path,
	chapter_title: str,
	crf: str,
	preset: str,
	chapters: list[dict] | None = None,
) -> None:
	duration = source_end - source_start
	relative_cuts = [
		(
			max(0.0, float(cut["start"]) - source_start),
			min(duration, float(cut["end"]) - source_start),
		)
		for cut in cuts
		if float(cut["end"]) > source_start and float(cut["start"]) < source_end
	]
	terms = [f"gte(t,{start:.3f})*lt(t,{end:.3f})" for start, end in relative_cuts if end > start]
	# 單一 select 表達式太長時，FFmpeg 的 expression parser 會失敗；分批串接。
	term_groups = [terms[index : index + 20] for index in range(0, len(terms), 20)]
	video_select = ",".join(
		f"select='not({'+'.join(group)})'" for group in term_groups
	) or "null"
	audio_select = ",".join(
		f"aselect='not({'+'.join(group)})'" for group in term_groups
	) or "anull"
	font_path = resolve_font_path()
	font_file = escape_filter_path(font_path) if font_path else "STHeiti"
	fonts_dir = resolve_fonts_dir(font_path)
	fonts_dir_value = escape_filter_path(fonts_dir) if fonts_dir else "/System/Library/Fonts"
	chapter_path.write_text(chapter_title, encoding="utf-8")
	chapter_rows = chapters or [{"id": 1, "title": chapter_title, "output_start": 0.0}]
	chapter_filters: list[str] = []
	for chapter in chapter_rows:
		chapter_id = int(chapter.get("id", len(chapter_filters) + 1))
		chapter_text_path = chapter_path.with_name(f"{chapter_path.stem}_{chapter_id:02d}.txt")
		chapter_text_path.write_text(str(chapter.get("title", "")), encoding="utf-8")
		chapter_file = escape_filter_path(chapter_text_path)
		chapter_start = float(chapter.get("output_start", 0.0))
		chapter_filters.append(
			"drawtext="
			f"fontfile='{font_file}':textfile='{chapter_file}':fontcolor=white:fontsize=34:x=48:y=42:box=1:boxcolor=0x9B0000CC:"
			f"boxborderw=14:enable='between(t,{chapter_start:.3f},{chapter_start + 5.0:.3f})'"
		)
	ass_file = escape_filter_path(ass_path)
	gradient = (
		"drawbox=x=0:y=400:w=iw:h=40:color=black@0.025:t=fill,"
		"drawbox=x=0:y=440:w=iw:h=40:color=black@0.045:t=fill,"
		"drawbox=x=0:y=480:w=iw:h=40:color=black@0.07:t=fill,"
		"drawbox=x=0:y=520:w=iw:h=40:color=black@0.095:t=fill,"
		"drawbox=x=0:y=560:w=iw:h=40:color=black@0.12:t=fill,"
		"drawbox=x=0:y=600:w=iw:h=40:color=black@0.15:t=fill,"
		"drawbox=x=0:y=640:w=iw:h=40:color=black@0.18:t=fill,"
		"drawbox=x=0:y=680:w=iw:h=40:color=black@0.20:t=fill,"
	)
	chapter_filter_text = ",".join(chapter_filters)
	video_filter = (
		f"{video_select},setpts=N/FRAME_RATE/TB,"
		f"{chapter_filter_text + ',' if chapter_filter_text else ''}{gradient}"
		f"subtitles=filename='{ass_file}':fontsdir='{fonts_dir_value}'"
	)
	audio_filter = f"{audio_select},asetpts=N/SR/TB,aresample=48000"
	command = [
		"ffmpeg",
		"-y",
		"-hide_banner",
		"-loglevel",
		"error",
		"-ss",
		f"{source_start:.3f}",
		"-t",
		f"{duration:.3f}",
		"-i",
		str(source),
		"-vf",
		video_filter,
		"-af",
		audio_filter,
		"-c:v",
		"libx264",
		"-preset",
		preset,
		"-crf",
		crf,
		"-pix_fmt",
		"yuv420p",
		"-r",
		"30",
		"-c:a",
		"aac",
		"-b:a",
		"192k",
		"-ar",
		"48000",
		"-shortest",
		"-movflags",
		"+faststart",
		str(output),
	]
	print(f"$ ffmpeg semantic filter（{len(relative_cuts)} 段剪除）", flush=True)
	subprocess.run(command, check=True)


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("edit", type=Path)
	parser.add_argument("--source", type=Path, required=True)
	parser.add_argument("--output-dir", type=Path, required=True)
	parser.add_argument("--chapter-title", default="客戶群定位與資訊服務案例")
	parser.add_argument("--subtitle-only", action="store_true", help="只清理字幕，不實際剪掉語音贅詞")
	parser.add_argument("--render", action="store_true")
	parser.add_argument("--crf", default="23")
	parser.add_argument("--preset", default="veryfast")
	args = parser.parse_args()

	edit = json.loads(args.edit.read_text(encoding="utf-8"))
	args.output_dir.mkdir(parents=True, exist_ok=True)
	source_start = float(edit["source_start"])
	source_end = float(edit["source_end"])
	raw_cuts = build_intervals(edit, physical_cut=not args.subtitle_only)
	cuts = frame_align_intervals(raw_cuts) if not args.subtitle_only else []
	ranges = build_ranges(args.source.resolve(), source_start, source_end, cuts)
	for item in ranges:
		item["source"] = "sample"
	edl = {
		"version": 1,
		"mode": "semantic-sample",
		"sources": {"sample": str(args.source.resolve())},
		"ranges": ranges,
		"cuts": cuts,
		"raw_cuts": raw_cuts,
		"source_start": source_start,
		"source_end": source_end,
		"total_duration_s": round(sum(item["end"] - item["start"] for item in ranges), 3),
	}
	edl_path = args.output_dir / "semantic_sample_edl.json"
	edl_path.write_text(json.dumps(edl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

	cues = build_cues(edit, source_start, cuts)
	cues_path = args.output_dir / "semantic_sample_cues.json"
	cues_path.write_text(json.dumps(cues, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	style = normalise_subtitle_style(
		edit.get("subtitle_style")
		or (edit.get("review") or {}).get("subtitle_style")
	)
	ass_path = args.output_dir / "semantic_sample_bilingual.ass"
	write_ass(
		cues,
		ass_path,
		zh_font_size=style["zh_font_size"],
		en_font_size=style["en_font_size"],
		show_english=style["show_english"],
	)

	chapters_path = args.output_dir / "semantic_sample_chapters.json"
	chapters_path.write_text(
		json.dumps(
			[{"id": 1, "title": args.chapter_title, "output_start": 0.0}],
			ensure_ascii=False,
			indent=2,
		)
		+ "\n",
		encoding="utf-8",
	)
	print(f"✅ EDL：{edl_path}")
	print(f"✅ 字幕：{ass_path}（{len(cues)} 條）")
	print(f"✅ 剪除：{len(cuts)} 段，共 {sum(item['end'] - item['start'] for item in cuts):.2f} 秒")

	if args.render:
		output = args.output_dir / "semantic_sample.mp4"
		chapter_path = args.output_dir / "semantic_sample_chapter.txt"
		render_filtered(
			args.source.resolve(),
			output,
			source_start,
			source_end,
			cuts,
			ass_path,
			chapter_path,
			args.chapter_title,
			args.crf,
			args.preset,
		)
		print(f"✅ 成片：{output}")


if __name__ == "__main__":
	main()

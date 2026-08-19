#!/usr/bin/env python3
"""以 shorts-master 的本地降級路線輸出直式短影音。"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

from render_semantic import escape_filter_path
from subtitle_layout import ASS_FONT_NAME, ASCII_TOKEN_RE, mixed_text_tokens, resolve_font_path, resolve_fonts_dir, visual_width, wrap_chinese
from generate_sfx import write_sfx
from talking_head_adapter import build_events, render_events


PROFILES = {
	"editorial": {"accent": "&H004DD5FF&", "back": "&HAA16181D&", "outline": "&H0016181D&", "bg": "0x16181D"},
	"variety": {"accent": "&H004DD5FF&", "back": "&HAA16181D&", "outline": "&H00000000&", "bg": "0x24140C"},
	"whiteboard": {"accent": "&H003D45D6&", "back": "&HCC2B2B2B&", "outline": "&H002B2B2B&", "bg": "0xFBF7EE"},
	"minimal": {"accent": "&H00FF840A&", "back": "&HAA101820&", "outline": "&H00101820&", "bg": "0x101820"},
	"neon": {"accent": "&H00F0FF00&", "back": "&HAA080A14&", "outline": "&H00080A14&", "bg": "0x080A14"},
	"terminal": {"accent": "&H0050B93F&", "back": "&HAA0D1117&", "outline": "&H000D1117&", "bg": "0x0D1117"},
}


def ass_time(seconds: float) -> str:
	centiseconds = max(0, int(round(seconds * 100)))
	hours, centiseconds = divmod(centiseconds, 360000)
	minutes, centiseconds = divmod(centiseconds, 6000)
	secs, centiseconds = divmod(centiseconds, 100)
	return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def escape_ass(text: str) -> str:
	return str(text).replace("{", r"\{").replace("}", r"\}").replace("\r", " ").replace("\n", " ")


def clean_text(value: object) -> str:
	return re.sub(r"\s+", " ", str(value or "")).strip()


def wrap_short_zh(text: str, font_size: int = 76, max_units: int | None = None) -> list[str]:
	text = clean_text(text)
	if max_units is None:
		max_units = 15 if font_size <= 80 else 11
	wrapped = wrap_chinese(text, max_width=940, font_size=font_size, max_units=max_units)
	return wrapped.split(r"\N") if wrapped else [""]


def wrap_short_en(text: str, max_chars: int = 42) -> list[str]:
	words = clean_text(text).split()
	lines: list[str] = []
	current = ""
	for word in words:
		candidate = f"{current} {word}".strip()
		if current and (len(candidate) > max_chars or visual_width(candidate, 38, english=True) > 940):
			lines.append(current)
			current = word
		else:
			current = candidate
	if current:
		lines.append(current)
	return lines or [""]


SHORT_MAX_CUE_UNITS = 28
SHORT_MAX_CUE_SECONDS = 5.4
SHORT_CAPTION_WIDTH = 940
SHORT_CAPTION_FONT_SIZE = 76
SHORT_CAPTION_MIN_FONT_SIZE = 42
TAIL_PAD_SECONDS = 0.65
SHORT_TERMINAL_CHARS = set("。！？；：.!?;:")
SHORT_BREAK_CHARS = SHORT_TERMINAL_CHARS | set("，、,.:")


def _short_units(text: str) -> int:
	text = clean_text(text)
	return max(1, math.ceil(visual_width(text, SHORT_CAPTION_FONT_SIZE) / SHORT_CAPTION_FONT_SIZE)) if text else 0


def _caption_break_positions(text: str) -> list[int]:
	"""只回傳自然標點後的位置；URL、版本號等 ASCII token 不能成為切點。"""
	positions: list[int] = []
	cursor = 0
	for token in mixed_text_tokens(text):
		cursor += len(token)
		if len(token) == 1 and token in SHORT_BREAK_CHARS:
			positions.append(cursor)
	return positions


def _ellipsis_within_caption_width(text: str, font_size: int) -> str:
	"""在固定可讀字級內縮略顯示文字；原始 cue 保留給審稿與後續輸出。"""
	if visual_width(text, font_size) <= SHORT_CAPTION_WIDTH:
		return text
	suffix = "…"
	visible = ""
	for char in text:
		if visual_width(visible + char + suffix, font_size) > SHORT_CAPTION_WIDTH:
			break
		visible += char
	return (visible.rstrip() + suffix) if visible.strip() else suffix


def _complete_caption_layout(text: str) -> tuple[list[str], int] | None:
	"""回傳不截字的可讀排版；無法安全排版時回傳 ``None``。"""
	for font_size in range(SHORT_CAPTION_FONT_SIZE, SHORT_CAPTION_MIN_FONT_SIZE - 1, -2):
		if visual_width(text, font_size) <= SHORT_CAPTION_WIDTH:
			return [text], font_size
	breaks = _caption_break_positions(text)
	for font_size in range(SHORT_CAPTION_FONT_SIZE, SHORT_CAPTION_MIN_FONT_SIZE - 1, -2):
		for split_at in sorted(breaks, key=lambda value: abs(value - len(text) / 2)):
			left, right = text[:split_at].strip(), text[split_at:].strip()
			if left and right and visual_width(left, font_size) <= SHORT_CAPTION_WIDTH and visual_width(right, font_size) <= SHORT_CAPTION_WIDTH:
				return [left, right], font_size
	return None


def _oversized_ascii_token(text: str, font_size: int) -> str | None:
	for token in mixed_text_tokens(text):
		if ASCII_TOKEN_RE.fullmatch(token) and visual_width(token, font_size) > SHORT_CAPTION_WIDTH:
			return token
	return None


def _safe_caption_display(token: str, font_size: int) -> str:
	"""只有獨立存在、無法逐字呈現的超長 ASCII token 才可於顯示層縮略。"""
	return _ellipsis_within_caption_width(token, font_size)


def fit_short_caption_lines(text: str) -> tuple[list[str], int]:
	"""優先單行縮小；真的要換行時，只在不屬於 ASCII token 的標點後切。"""
	text = clean_text(text)
	if not text:
		return [""], SHORT_CAPTION_FONT_SIZE
	layout = _complete_caption_layout(text)
	if layout is not None:
		return layout
	# 網址／版本號等單一 ASCII token 不可安全斷行，才允許顯示層以省略號保留前綴。
	oversized_token = _oversized_ascii_token(text, SHORT_CAPTION_MIN_FONT_SIZE)
	if oversized_token:
		before, after = text.split(oversized_token, 1)
		if not re.search(r"[\u3400-\u9fffA-Za-z0-9]", before + after):
			return [_safe_caption_display(oversized_token, SHORT_CAPTION_MIN_FONT_SIZE)], SHORT_CAPTION_MIN_FONT_SIZE
	# 中文口語內容不能默默截字或在詞中斷行，交回語意階段人工切分。
	raise ValueError("短字幕無安全標點且超過可讀範圍，請在語意編輯階段分句")


def _punctuation_only(text: str) -> bool:
	return not re.search(r"[\u3400-\u9fffA-Za-z0-9]", clean_text(text))


def _join_short_zh(left: str, right: str) -> str:
	left = clean_text(left)
	right = clean_text(right)
	if not left:
		return right
	if not right:
		return left
	separator = " " if left[-1].isascii() and right[0].isascii() else ""
	return left + separator + right


def merge_short_cues(edit: dict, source_start: float, source_end: float) -> list[dict]:
	"""合併模型碎句，避免短片出現單字／標點孤兒字幕。"""
	candidates: list[dict] = []
	for cue in edit.get("cues", []):
		cue_start = float(cue.get("source_start", 0.0))
		cue_end = float(cue.get("source_end", 0.0))
		if cue_end <= source_start or cue_start >= source_end:
			continue
		text = clean_text(cue.get("zh"))
		if not text:
			continue
		candidates.append(
			{
				"source_start": max(source_start, cue_start),
				"source_end": min(source_end, cue_end),
				"zh": text,
			}
		)
	candidates.sort(key=lambda item: (item["source_start"], item["source_end"]))
	merged: list[dict] = []
	current: dict | None = None
	for candidate in candidates:
		if current is None:
			current = candidate
			continue
		gap = candidate["source_start"] - current["source_end"]
		combined_text = _join_short_zh(current["zh"], candidate["zh"])
		combined_units = _short_units(combined_text)
		combined_duration = candidate["source_end"] - current["source_start"]
		must_join = (
			_punctuation_only(candidate["zh"])
			or _short_units(current["zh"]) <= 2
			or _short_units(candidate["zh"]) <= 2
		)
		should_break = (
			not must_join
			and current["zh"][-1:] in SHORT_TERMINAL_CHARS
		) or (
			not must_join
			and gap >= 0.55
			and _short_units(current["zh"]) >= 6
		) or combined_units > SHORT_MAX_CUE_UNITS or combined_duration > SHORT_MAX_CUE_SECONDS
		if should_break:
			merged.append(current)
			current = candidate
		else:
			current["source_end"] = candidate["source_end"]
			current["zh"] = combined_text
	if current is not None:
		merged.append(current)

	# 太短的完整詞組也不應一閃而過；併到下一個自然 cue，讓觀眾有時間讀完。
	smoothed: list[dict] = []
	index = 0
	while index < len(merged):
		item = merged[index]
		if index + 1 < len(merged):
			next_item = merged[index + 1]
			combined_text = _join_short_zh(item["zh"], next_item["zh"])
			combined_duration = next_item["source_end"] - item["source_start"]
			if (
				item["source_end"] - item["source_start"] < 0.75
				and _short_units(combined_text) <= SHORT_MAX_CUE_UNITS
				and combined_duration <= SHORT_MAX_CUE_SECONDS
			):
				item = {
					"source_start": item["source_start"],
					"source_end": next_item["source_end"],
					"zh": combined_text,
				}
				index += 1
		smoothed.append(item)
		index += 1

	# 最後仍剩一個極短片段時，寧可和前句合併，也不輸出單字畫面。
	if len(smoothed) > 1 and _short_units(smoothed[-1]["zh"]) <= 2:
		last = smoothed.pop()
		smoothed[-1]["source_end"] = last["source_end"]
		smoothed[-1]["zh"] = _join_short_zh(smoothed[-1]["zh"], last["zh"])
	return smoothed


def split_short_text(text: str) -> list[str]:
	"""只在安全標點後拆 cue；無安全切點時交由字幕檢查要求語意重切。"""
	text = clean_text(text)
	if not text or _complete_caption_layout(text) is not None:
		return [text]
	positions = _caption_break_positions(text)
	if not positions:
		return [text]
	chunks: list[str] = []
	cursor = 0
	for position in positions:
		chunk = text[cursor:position].strip()
		if chunk:
			chunks.append(chunk)
		cursor = position
	tail = text[cursor:].strip()
	if tail:
		chunks.append(tail)
	return chunks or [text]


def split_caption(cue: dict, segment_start: float, cue_start: float, cue_end: float, speed: float) -> list[dict]:
	zh_parts = split_short_text(cue.get("zh", ""))
	parts = max(1, len(zh_parts))
	result: list[dict] = []
	for index, zh in enumerate(zh_parts):
		part_start = ((cue_start - segment_start) + (cue_end - cue_start) * index / parts) / speed
		part_end = ((cue_start - segment_start) + (cue_end - cue_start) * (index + 1) / parts) / speed
		result.append(
			{
				"start": round(part_start, 3),
				"end": round(part_end, 3),
				"zh": zh,
				"en": "",
			}
		)
	return result


def build_captions(edit: dict, source_start: float, source_end: float, speed: float) -> list[dict]:
	result: list[dict] = []
	for cue in merge_short_cues(edit, source_start, source_end):
		start = float(cue["source_start"])
		end = float(cue["source_end"])
		result.extend(split_caption(cue, source_start, start, end, speed))
	return result


def write_ass(
	captions: list[dict],
	output: Path,
	title: str,
	style_name: str,
	duration: float,
	cta_text: str = "",
) -> None:
	profile = PROFILES[style_name]
	font_path = resolve_font_path()
	font_name = ASS_FONT_NAME if font_path else "Arial"
	lines = [
		"[Script Info]",
		"ScriptType: v4.00+",
		"PlayResX: 1080",
		"PlayResY: 1920",
		"ScaledBorderAndShadow: yes",
		"WrapStyle: 2",
		"",
		"[V4+ Styles]",
		"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
		f"Style: Caption,{font_name},76,&H00FFFFFF,&H00FFFFFF,{profile['outline']},{profile['back']},-1,0,0,0,100,100,0,0,1,5,3,2,42,42,260,1",
		f"Style: Emph,{font_name},76,&H00FFFFFF,{profile['accent']},{profile['outline']},{profile['back']},-1,0,0,0,100,100,0,0,1,5,3,2,34,34,270,1",
		f"Style: Title,{font_name},68,{profile['accent']},&H00FFFFFF,{profile['outline']},{profile['back']},-1,0,0,0,100,100,2,0,3,4,3,8,48,48,120,1",
		f"Style: CTA,{font_name},58,&H00FFFFFF,&H00FFFFFF,{profile['outline']},{profile['back']},-1,0,0,0,100,100,0,0,3,5,3,8,48,48,360,1",
		"",
		"[Events]",
		"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
	]
	title_text = escape_ass(title)[:42]
	lines.append(
		f"Dialogue: 2,{ass_time(0)},{ass_time(min(3.2, duration))},Title,,0,0,0,,"
		f"{{\\fad(0,180)\\fscx75\\fscy75\\t(0,220,\\fscx100\\fscy100)}}{title_text}"
	)
	if cta_text and duration > 5:
		cta_start = max(0.0, duration - 4.8)
		cta_end = max(cta_start + 0.4, duration - 0.35)
		cta = escape_ass(cta_text)
		lines.append(
			f"Dialogue: 3,{ass_time(cta_start)},{ass_time(cta_end)},CTA,,0,0,0,,"
			f"{{\\fad(220,260)\\pos(540,360)}}{cta}"
		)
	for index, caption in enumerate(captions):
		zh_raw = clean_text(caption["zh"])
		# 字幕維持同一套基準大小；只有太長時縮小，換行只發生在標點之後。
		style = "Emph" if index == 0 or _short_units(zh_raw) <= 14 else "Caption"
		zh_lines, font_size = fit_short_caption_lines(zh_raw)
		zh = r"\N".join(escape_ass(line) for line in zh_lines[:2])
		en = escape_ass(caption.get("en", ""))
		text = f"{{\\fs{font_size}\\fad(60,60)}}{zh}"
		if en:
			text += f"\\N{{\\fs38\\c&H00D9D9D9&}}{en}"
		lines.append(
			f"Dialogue: 1,{ass_time(caption['start'])},{ass_time(caption['end'])},{style},,0,0,0,,{text}"
		)
	output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def atempo_filter(speed: float) -> str:
	parts: list[str] = []
	remaining = speed
	while remaining > 2.0:
		parts.append("atempo=2.0")
		remaining /= 2.0
	while remaining < 0.5:
		parts.append("atempo=0.5")
		remaining /= 0.5
	parts.append(f"atempo={remaining:.6f}")
	return ",".join(parts)


def render_segment(
	source: Path,
	output: Path,
	ass: Path,
	start: float,
	duration: float,
	speed: float,
	style_name: str,
	animation_events: list[dict] | None = None,
	bgm: Path | None = None,
	sfx: Path | None = None,
) -> None:
	profile = PROFILES[style_name]
	ass_file = escape_filter_path(ass)
	fonts_dir = resolve_fonts_dir(resolve_font_path())
	fonts_dir_value = escape_filter_path(fonts_dir) if fonts_dir else "/System/Library/Fonts"
	filters = [
		f"[0:v]setpts=PTS/{speed:.6f},split=2[bg][fg]",
		f"[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
		f"boxblur=20:10,eq=brightness=-0.08:saturation=0.78[bgv]",
		f"[fg]scale=1080:-2:force_original_aspect_ratio=decrease,"
		f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color={profile['bg']}[fgv]",
		f"[bgv][fgv]overlay=0:0[base]",
	]
	input_args = [
		"-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source)
	]
	last_video = "base"
	for index, event in enumerate(animation_events or [], start=1):
		frames = Path(event["frames"])
		start_time = float(event["start"])
		end_time = start_time + float(event["duration"])
		input_args.extend(["-framerate", str(int(event.get("fps", 30))), "-i", str(frames / "ov_%04d.png")])
		filters.append(
			f"[{index}:v]format=rgba,setpts=PTS-STARTPTS+{start_time:.3f}/TB[anim{index}]"
		)
		out_label = f"ov{index}"
		filters.append(
			f"[{last_video}][anim{index}]overlay=0:0:format=auto:"
			f"enable='between(t,{start_time:.3f},{end_time:.3f})'[{out_label}]"
		)
		last_video = out_label
	# 尾端先複製最後一幀／補靜音，再淡出；不讓淡出吃掉最後一句口白。
	content_duration = max(0.1, duration / speed)
	rendered_duration = content_duration + TAIL_PAD_SECONDS
	filters.append(
		f"[{last_video}]tpad=stop_mode=clone:stop_duration={TAIL_PAD_SECONDS:.3f},"
		f"subtitles=filename='{ass_file}':fontsdir='{fonts_dir_value}',"
		f"fade=t=out:st={max(0.0, rendered_duration - 0.45):.3f}:d=0.45[v]"
	)

	map_audio = "0:a:0?"
	audio_args: list[str] = [
		"-af",
		f"{atempo_filter(speed)},apad=pad_dur={TAIL_PAD_SECONDS:.3f},"
		f"afade=t=out:st={max(0.0, rendered_duration - 0.55):.3f}:d=0.55",
	]
	if bgm or sfx:
		music_end = rendered_duration
		mix_labels = []
		# 混入 BGM／SFX 時保留人聲頭部空間，避免總音量突然爆高。
		filters.append(
			f"[0:a:0]aresample=48000,{atempo_filter(speed)},apad=pad_dur={TAIL_PAD_SECONDS:.3f},volume=0.5[voice]"
		)
		mix_labels.append("[voice]")
		next_audio_index = 1 + len(animation_events or [])
		if bgm:
			bgm_index = next_audio_index
			input_args.extend(["-stream_loop", "-1", "-i", str(bgm)])
			filters.append(
				f"[{bgm_index}:a:0]aresample=48000,atrim=0:{music_end:.3f},volume=0.12,"
				f"afade=t=in:st=0:d=0.8,afade=t=out:st={max(0.0, music_end - 1.8):.3f}:d=1.6[music]"
			)
			mix_labels.append("[music]")
			next_audio_index += 1
		if sfx:
			sfx_index = next_audio_index
			input_args.extend(["-i", str(sfx)])
			filters.append(f"[{sfx_index}:a:0]aresample=48000,atrim=0:{music_end:.3f},volume=0.65[sfx]")
			mix_labels.append("[sfx]")
		filters.append(
			"".join(mix_labels)
			+ f"amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2:normalize=0,"
			f"alimiter=limit=0.94,afade=t=out:st={max(0.0, music_end - 0.55):.3f}:d=0.55[a]"
		)
		map_audio = "[a]"
		audio_args = []

	command = [
		"ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
		*input_args,
		"-filter_complex", ";".join(filters), "-map", "[v]", "-map", map_audio,
		*audio_args,
		"-t", f"{rendered_duration:.3f}",
		"-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-r", "30",
		"-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(output),
	]
	subprocess.run(command, check=True)


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("edit", type=Path)
	parser.add_argument("segments", type=Path)
	parser.add_argument("--source", type=Path, required=True)
	parser.add_argument("--output-dir", type=Path, required=True)
	parser.add_argument("--speed", type=float, default=1.15)
	parser.add_argument("--style", choices=sorted(PROFILES), default="editorial")
	parser.add_argument("--animation", choices=("none", "talking-head"), default="none")
	parser.add_argument("--broll", choices=("none", "local"), default="none", help="local Image2-style context cards")
	parser.add_argument("--bgm", type=Path, help="optional local BGM file")
	parser.add_argument("--generate-bgm", action="store_true", help="generate a local synthetic BGM")
	parser.add_argument("--generate-sfx", action="store_true", help="generate local transition/checklist/stamp sound effects")
	parser.add_argument("--cta", default="", help="optional final CTA text")
	parser.add_argument("--limit", type=int, default=0, help="render only the first N segments")
	parser.add_argument("--render", action="store_true")
	args = parser.parse_args()
	if args.speed <= 0:
		raise SystemExit("--speed 必須大於 0")
	if args.limit < 0:
		raise SystemExit("--limit 不可小於 0")
	if args.bgm and args.generate_bgm:
		raise SystemExit("--bgm 與 --generate-bgm 不可同時使用")
	edit = json.loads(args.edit.read_text(encoding="utf-8"))
	segment_payload = json.loads(args.segments.read_text(encoding="utf-8"))
	args.output_dir.mkdir(parents=True, exist_ok=True)
	bgm_path = args.bgm.resolve() if args.bgm else None
	if args.generate_bgm:
		bgm_path = args.output_dir / "generated_bgm.wav"
		if args.render and not bgm_path.exists():
			subprocess.run([
				sys.executable,
				str(Path(__file__).with_name("generate_bgm.py")),
				str(bgm_path),
				"--duration",
				"90",
			], check=True)
	if bgm_path and not bgm_path.is_file():
		raise SystemExit(f"BGM 不存在：{bgm_path}")
	outputs: list[dict] = []
	segments = segment_payload.get("segments", [])
	if args.limit:
		segments = segments[: args.limit]
	for segment in segments:
		start = float(segment["source_start"])
		end = float(segment["source_end"])
		duration = end - start
		output_duration = duration / args.speed
		captions = build_captions(edit, start, end, args.speed)
		ass = args.output_dir / f"short_{int(segment['id']):02d}.ass"
		output = args.output_dir / f"short_{int(segment['id']):02d}.mp4"
		write_ass(
			captions,
			ass,
			str(segment.get("title", "精華短影音")),
			args.style,
			output_duration,
			args.cta,
		)
		use_talking_head = args.animation == "talking-head" or args.broll == "local"
		animation_events = (
			build_events(captions, output_duration, include_broll=args.broll == "local")
			if use_talking_head
			else []
		)
		animation_dir = args.output_dir / f".talking-head-{int(segment['id']):02d}"
		rendered_events = render_events(animation_events, animation_dir) if args.render and animation_events else []
		sfx_path = None
		if args.generate_sfx and args.render and rendered_events:
			sfx_path = args.output_dir / f"short_{int(segment['id']):02d}_sfx.wav"
			write_sfx(sfx_path, rendered_events, output_duration)
		row = {
			**segment,
			"speed": args.speed,
			"style": args.style,
			"animation": args.animation,
			"broll": args.broll,
			"animation_events": [{k: v for k, v in event.items() if k != "frames"} for event in rendered_events],
			"bgm": str(bgm_path) if bgm_path else None,
			"sfx": str(sfx_path) if sfx_path else None,
			"cta": args.cta,
			"content_duration": round(output_duration, 3),
			"duration": round(output_duration + TAIL_PAD_SECONDS, 3),
			"ass": str(ass),
			"output": str(output),
			"caption_count": len(captions),
		}
		outputs.append(row)
		if args.render:
			render_segment(
				args.source.resolve(),
				output,
				ass,
				start,
				duration,
				args.speed,
				args.style,
				rendered_events,
				bgm_path,
				sfx_path,
			)
			if animation_dir.exists():
				shutil.rmtree(animation_dir)
			print(f"✅ short_{int(segment['id']):02d}: {output}")
	manifest = {
		"schema_version": 1,
		"tool": "awesome-janson",
		"mode": "shorts-master+talking-head-video-cut-local",
		"style": args.style,
		"animation": args.animation,
		"broll": args.broll,
		"speed": args.speed,
		"bgm": str(bgm_path) if bgm_path else None,
		"sfx": bool(args.generate_sfx),
		"cta": args.cta,
		"segments": outputs,
	}
	(args.output_dir / "shorts_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
	print(f"✅ 字幕／manifest：{args.output_dir}")


if __name__ == "__main__":
	main()

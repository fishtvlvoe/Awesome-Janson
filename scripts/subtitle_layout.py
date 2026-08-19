#!/usr/bin/env python3
"""跨平台字幕字體與語意換行工具。"""
from __future__ import annotations

import math
import os
import re
from pathlib import Path


ASS_FONT_NAME = "Source Han Sans TC"
ZH_FONT_SIZE = 50
EN_FONT_SIZE = 30
MAX_TEXT_WIDTH = 1080.0
MAX_ZH_UNITS = 22
MAX_EN_CHARS = 60
ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9@%+._~:/?#\[\]&=\-]*")
TRAILING_ASCII_PUNCTUATION = ".,;:!?"


def mixed_text_tokens(text: str) -> list[str]:
	"""將 URL、版本號、email 等 ASCII token 視為不可分割的字幕單位。"""
	result: list[str] = []
	cursor = 0
	for match in ASCII_TOKEN_RE.finditer(text):
		result.extend(text[cursor : match.start()])
		token = match.group()
		core = token.rstrip(TRAILING_ASCII_PUNCTUATION)
		if core:
			result.append(core)
		result.extend(token[len(core) :])
		cursor = match.end()
	result.extend(text[cursor:])
	return result


def resolve_font_path() -> Path | None:
	"""尋找思源黑體；不同平台找不到時再使用系統 CJK 字體。"""
	env_path = os.environ.get("AWESOME_JANSON_FONT")
	candidates = []
	if env_path:
		candidates.append(Path(env_path).expanduser())
	candidates.extend(
		[
			Path.home() / "Library/Fonts/SourceHanSansTC-Medium.otf",
			Path.home() / "Library/Fonts/SourceHanSansTC-Regular.otf",
			Path.home() / ".local/share/fonts/SourceHanSansTC-Regular.otf",
			Path.home() / ".fonts/SourceHanSansTC-Regular.otf",
			Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts/SourceHanSansTC-Regular.otf",
			Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/SourceHanSansTC-Regular.otf",
			Path("/Library/Fonts/SourceHanSansTC-Regular.otf"),
			Path("/System/Library/Fonts/STHeiti Medium.ttc"),
			Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
			Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
			Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
		])
	for path in candidates:
		if str(path) and path.is_file():
			return path
	return None


def resolve_fonts_dir(font_path: Path | None) -> Path | None:
	return font_path.parent if font_path else None


def _char_width(char: str, font_size: float, english: bool = False) -> float:
	if char.isspace():
		return font_size * 0.28
	if ord(char) >= 0x2E80:
		return font_size
	if char in "，。！？；：、（）【】「」『』〈〉《》〈〉,.!?;:()[]{}":
		return font_size * (0.5 if not english else 0.35)
	return font_size * (0.56 if english else 0.62)


def visual_width(text: str, font_size: float, english: bool = False) -> float:
	return sum(_char_width(char, font_size, english=english) for char in text)


def _display_units(text: str, font_size: float) -> int:
	units = 0
	for token in mixed_text_tokens(text):
		if ASCII_TOKEN_RE.fullmatch(token):
			units += max(1, round(visual_width(token, font_size, english=True) / font_size))
		else:
			units += 1
	return units


def wrap_chinese(
	text: str,
	max_width: float = MAX_TEXT_WIDTH,
	font_size: float = ZH_FONT_SIZE,
	max_units: int = MAX_ZH_UNITS,
) -> str:
	"""中文依視覺寬度換行，避免長句超出 16:9 畫面。"""
	lines: list[str] = []
	for source_line in re.split(r"\r?\n", text.strip()):
		current = ""
		# 連續英數、URL 與專有名詞視為一個 token，不能在 Computex、Wi-Fi、https:// 中間斷行。
		tokens = mixed_text_tokens(source_line)
		for token in tokens:
			candidate = current + token
			if current and (
				visual_width(candidate, font_size) > max_width
				or _display_units(candidate, font_size) > max_units
			):
				lines.append(current.rstrip())
				current = token
			else:
				current = candidate
		if current:
			lines.append(current.rstrip())
	return r"\N".join(lines)


def _split_tokens(text: str, english: bool) -> list[str]:
	if english:
		return re.findall(r"\S+\s*", text.strip())
	return mixed_text_tokens(text.strip())


def _token_units(token: str, english: bool) -> float:
	if english:
		return max(1.0, len(token.rstrip()) * 0.56)
	return float(_display_units(token, ZH_FONT_SIZE))


def split_text_parts(text: str, parts: int, english: bool = False) -> list[str]:
	"""在自然標點或單字邊界切成固定數量，供字幕 cue 硬上限使用。"""
	if parts <= 1 or not text.strip():
		return [text.strip()]
	tokens = _split_tokens(text, english)
	if len(tokens) <= 1:
		return [text.strip()]
	units = [_token_units(token, english) for token in tokens]
	total = sum(units)
	punctuation = set("，。！？；：、,.!?;:")
	result: list[str] = []
	start = 0
	for part_index in range(parts - 1):
		remaining_parts = parts - part_index
		remaining_tokens = len(tokens) - start
		if remaining_tokens <= remaining_parts - 1:
			break
		target = sum(units[start:]) / remaining_parts
		cumulative = 0.0
		candidates: list[tuple[float, int]] = []
		for index in range(start + 1, len(tokens) - (remaining_parts - 2)):
			cumulative += units[index - 1]
			last = tokens[index - 1].rstrip()
			penalty = 0.0 if (last and last[-1] in punctuation) else 3.0
			candidates.append((abs(cumulative - target) + penalty, index))
		_, split_at = min(candidates)
		result.append("".join(tokens[start:split_at]).strip())
		start = split_at
	result.append("".join(tokens[start:]).strip())
	return [item for item in result if item]


def split_subtitle_cue(cue: dict) -> list[dict]:
	"""限制每個字幕事件最多兩行，超長句拆成多個有時間的 cue。"""
	zh = re.sub(r"\s*\r?\n\s*", "", str(cue.get("zh", "")).strip())
	en = re.sub(r"\s*\r?\n\s*", " ", str(cue.get("en", "")).strip())
	normalised = {**cue, "zh": zh, "en": en}
	zh_parts = max(1, math.ceil(_display_units(zh, ZH_FONT_SIZE) / (MAX_ZH_UNITS * 2)))
	en_parts = max(1, math.ceil(len(en) / (MAX_EN_CHARS * 2)))
	# 單字長度與標點分布可能讓換行器產生第三行，第三行也要觸發 cue 拆分。
	wrapped_zh_lines = len(wrap_chinese(zh).split(r"\N")) if zh else 0
	wrapped_en_lines = len(wrap_english(en).split(r"\N")) if en else 0
	parts = max(zh_parts, en_parts, math.ceil(wrapped_zh_lines / 2), math.ceil(wrapped_en_lines / 2))
	if parts <= 1:
		return [normalised]
	zh_chunks = split_text_parts(zh, parts, english=False)
	en_chunks = split_text_parts(en, parts, english=True) if en else [""] * parts
	while len(zh_chunks) < parts:
		zh_chunks.append("")
	while len(en_chunks) < parts:
		en_chunks.append("")
	start = float(cue["start"])
	end = float(cue["end"])
	weights = [max(1.0, _display_units(zh_chunks[index], ZH_FONT_SIZE), len(en_chunks[index]) * 0.35) for index in range(parts)]
	total_weight = sum(weights)
	result: list[dict] = []
	cursor = start
	for index in range(parts):
		chunk_end = end if index == parts - 1 else cursor + (end - start) * weights[index] / total_weight
		item = dict(normalised)
		item["start"] = round(cursor, 3)
		item["end"] = round(chunk_end, 3)
		item["zh"] = zh_chunks[index] if index < len(zh_chunks) else ""
		item["en"] = en_chunks[index] if index < len(en_chunks) else ""
		result.append(item)
		cursor = chunk_end
	return result


def wrap_english(
	text: str,
	max_width: float = MAX_TEXT_WIDTH,
	font_size: float = EN_FONT_SIZE,
	max_chars: int = MAX_EN_CHARS,
) -> str:
	"""英文以單字換行，避免在單字中間斷開。"""
	lines: list[str] = []
	for source_line in re.split(r"\r?\n", text.strip()):
		current = ""
		for token in re.findall(r"\S+\s*", source_line):
			candidate = current + token
			if current and (
				visual_width(candidate.rstrip(), font_size, english=True) > max_width
				or len(candidate.rstrip()) > max_chars
			):
				lines.append(current.rstrip())
				current = token.lstrip()
			else:
				current = candidate
		if current:
			lines.append(current.rstrip())
	return r"\N".join(lines)

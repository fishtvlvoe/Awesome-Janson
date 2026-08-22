#!/usr/bin/env python3
"""產生不依賴外部 API 的直式情境 B-roll 卡。

這是 Image2 風格的本地 fallback：用逐字稿已有內容做成可動的資訊圖卡，
不下載圖片、不捏造客戶成果或數字；未來若接入外部圖片模型，只需替換此 adapter。
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from talking_head_adapter import anim_lib
from subtitle_layout import mixed_text_tokens


W, H = 1080, 1920
# 與 render_shorts editorial 背景 0x16181D 對齊，避免 B-roll 跳出另一套底色。
DARK = (22, 24, 29)
PANEL = (30, 38, 45)
PANEL_2 = (38, 48, 55)
TEAL = (20, 200, 190)
GOLD = (255, 214, 0)
WHITE = (255, 255, 255)
MUTED = (150, 170, 166)
BLUE = (66, 133, 226)
GREEN = (73, 176, 105)
ORANGE = (235, 151, 45)
RED = (226, 86, 74)


def _c01(value: float) -> float:
	return max(0.0, min(1.0, value))


def _eoc(value: float) -> float:
	value = _c01(value)
	return 1 - (1 - value) ** 3


def _alpha(color: tuple[int, int, int], opacity: float) -> tuple[int, int, int, int]:
	return (*color, int(255 * _c01(opacity)))


def _font(weight: str, size: int):
	return anim_lib.F(weight, size)


def _wrap(text: str, font, max_width: int, max_lines: int = 2) -> list[str]:
	text = " ".join(str(text or "").split())
	if not text:
		return [""]
	dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
	lines: list[str] = []
	current = ""
	for char in text:
		candidate = current + char
		if current and dummy.textlength(candidate, font=font) > max_width:
			lines.append(current.strip())
			current = char
		else:
			current = candidate
	if current.strip():
		lines.append(current.strip())
	if len(lines) <= max_lines:
		return lines
	# B-roll 只顯示短重點；超過兩行時保留語意開頭，完整內容仍在下方字幕。
	return [lines[0], "".join(lines[1:])[:18] + ("…" if len("".join(lines[1:])) > 18 else "")]


def _draw_lines(draw: ImageDraw.ImageDraw, lines: list[str], center_x: int, top: int, font, fill, line_gap: int = 12) -> int:
	line_height = max(42, font.getbbox("國")[3] - font.getbbox("國")[1])
	for index, line in enumerate(lines):
		width = draw.textlength(line, font=font)
		draw.text((center_x - width / 2, top + index * (line_height + line_gap)), line, font=font, fill=fill)
	return top + len(lines) * (line_height + line_gap)


def _text_block(
	draw: ImageDraw.ImageDraw,
	text: str,
	center_x: int,
	top: int,
	font,
	fill: tuple[int, int, int, int],
	max_width: int,
	line_gap: int = 12,
) -> int:
	return _draw_lines(draw, _wrap(text, font, max_width), center_x, top, font, fill, line_gap)


def _headline_break_positions(text: str) -> list[int]:
	"""只允許在 ASCII token 外的標點後換行，避免 URL 被切成 ``https:``。"""
	positions: list[int] = []
	cursor = 0
	for token in mixed_text_tokens(text):
		cursor += len(token)
		if len(token) == 1 and token in "，。！？；：、,.!?;:":
			positions.append(cursor)
	return positions


def _truncate_headline(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> str:
	"""無安全換行點的超長標題以尾端省略號縮略，保留完整 token 前綴。"""
	if draw.textlength(text, font=font) <= max_width:
		return text
	suffix = "…"
	fitted = ""
	for char in text:
		if draw.textlength(fitted + char + suffix, font=font) > max_width:
			break
		fitted += char
	return (fitted + suffix) if fitted else suffix


def _fit_headline(text: str, max_width: int = 780) -> tuple[list[str], object]:
	"""標題先縮成一行；只有安全標點可切時才使用兩行。"""
	dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
	for size in range(64, 43, -2):
		font = _font("H", size)
		if dummy.textlength(text, font=font) <= max_width:
			return [text], font
	breaks = _headline_break_positions(text)
	for size in range(60, 43, -2):
		font = _font("H", size)
		for split_at in sorted(breaks, key=lambda value: abs(value - len(text) / 2)):
			left, right = text[:split_at].strip(), text[split_at:].strip()
			if left and right and dummy.textlength(left, font=font) <= max_width and dummy.textlength(right, font=font) <= max_width:
				return [left, right], font
	font = _font("H", 42)
	return [_truncate_headline(text, font, max_width, dummy)], font


def _arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color, width: int = 8) -> None:
	draw.line([start, end], fill=color, width=width)
	angle = math.atan2(end[1] - start[1], end[0] - start[0])
	length = 22
	left = (
		end[0] - length * math.cos(angle - math.pi / 6),
		end[1] - length * math.sin(angle - math.pi / 6),
	)
	right = (
		end[0] - length * math.cos(angle + math.pi / 6),
		end[1] - length * math.sin(angle + math.pi / 6),
	)
	draw.polygon([end, left, right], fill=color)


def _scene_network(draw: ImageDraw.ImageDraw, progress: float, opacity: float) -> None:
	cx = W // 2
	nodes = [(275, 800, "客戶", TEAL), (540, 610, "服務", GOLD), (805, 800, "引薦", GREEN)]
	for left, right in [((310, 770), (505, 635)), ((575, 635), (770, 770))]:
		_arrow(draw, left, right, _alpha(TEAL, opacity * progress), 7)
	for x, y, label, color in nodes:
		radius = int(82 * (0.88 + 0.12 * progress))
		draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=_alpha(PANEL_2, opacity), outline=_alpha(color, opacity), width=7)
		font = _font("H", 34)
		width = draw.textlength(label, font=font)
		draw.text((x - width / 2, y - 21), label, font=font, fill=_alpha(WHITE, opacity))
	# 中央的循環線，讓靜態卡也有動感。
	arc_box = [cx - 250, 430, cx + 250, 930]
	draw.arc(arc_box, 210, 330, fill=_alpha(GOLD, opacity * progress), width=5)


def _scene_funnel(draw: ImageDraw.ImageDraw, progress: float, opacity: float) -> None:
	cx = W // 2
	levels = [(BLUE, "一般引薦", 760), (GREEN, "理想引薦", 895), (ORANGE, "夢幻引薦", 1030)]
	for index, (color, label, y) in enumerate(levels):
		width = int((355 - index * 88) * (0.84 + 0.16 * progress))
		height = 106
		x = cx - width // 2
		points = [(x + 28, y), (x + width - 28, y), (x + width - 64, y + height), (x + 64, y + height)]
		draw.polygon(points, fill=_alpha(color, opacity * (0.82 + 0.18 * progress)))
		draw.line(points + [points[0]], fill=_alpha(WHITE, opacity * 0.65), width=4)
		font = _font("H", 36)
		text_width = draw.textlength(label, font=font)
		draw.text((cx - text_width / 2, y + 31), label, font=font, fill=_alpha(WHITE, opacity))
	# 小光點沿漏斗向下走，取代一成不變的靜態圖。
	point_y = 680 + int((progress * 420) % 420)
	draw.ellipse([cx - 10, point_y - 10, cx + 10, point_y + 10], fill=_alpha(GOLD, opacity))


def _scene_pipeline(draw: ImageDraw.ImageDraw, progress: float, opacity: float) -> None:
	# 「接水管」用抽象管線表示，不加入未在逐字稿出現的成果數字。
	font = _font("H", 34)
	labels = [(215, "客戶", TEAL), (540, "協力廠商", GOLD), (865, "服務", GREEN)]
	for index in range(2):
		start_x = labels[index][0] + 92
		end_x = labels[index + 1][0] - 92
		y = 820 + int(8 * math.sin(progress * math.pi * 2 + index))
		draw.line([(start_x, y), (end_x, y)], fill=_alpha(GOLD, opacity), width=26)
		draw.line([(start_x, y - 14), (end_x, y - 14)], fill=_alpha(WHITE, opacity * 0.38), width=4)
		_arrow(draw, (end_x - 36, y), (end_x, y), _alpha(GOLD, opacity), 8)
	for x, label, color in labels:
		draw.rounded_rectangle([x - 92, 730, x + 92, 910], radius=28, fill=_alpha(PANEL_2, opacity), outline=_alpha(color, opacity), width=7)
		width = draw.textlength(label, font=font)
		draw.text((x - width / 2, 800), label, font=font, fill=_alpha(WHITE, opacity))
	


def _scene_people(draw: ImageDraw.ImageDraw, progress: float, opacity: float) -> None:
	"""以抽象人物與握手動作表現引薦情境，不虛構真人或客戶成果。"""
	people = [(285, "引薦", TEAL), (540, "合作", GOLD), (795, "客戶", GREEN)]
	for index, (x, label, color) in enumerate(people):
		y = 790 + int(22 * math.sin(progress * math.pi + index * 1.4))
		draw.ellipse([x - 58, y - 180, x + 58, y - 64], fill=_alpha(color, opacity), outline=_alpha(WHITE, opacity * 0.55), width=4)
		draw.rounded_rectangle([x - 92, y - 48, x + 92, y + 148], radius=46, fill=_alpha(PANEL_2, opacity), outline=_alpha(color, opacity), width=6)
		font = _font("H", 32)
		width = draw.textlength(label, font=font)
		draw.text((x - width / 2, y + 24), label, font=font, fill=_alpha(WHITE, opacity))
	# 中間雙手向彼此靠攏，讓圖像在兩秒內完成一個可讀動作。
	hand_offset = int(70 * (1.0 - _eoc(progress)))
	draw.line([(420 - hand_offset, 940), (530, 1000)], fill=_alpha(GOLD, opacity), width=24)
	draw.line([(660 + hand_offset, 940), (550, 1000)], fill=_alpha(GOLD, opacity), width=24)
	draw.ellipse([510, 975, 570, 1035], fill=_alpha(GOLD, opacity))


def _scene_table(draw: ImageDraw.ImageDraw, progress: float, opacity: float) -> None:
	"""以流程表格取代杜撰數字的圖表；欄位只描述角色與下一步。"""
	left, top, right, bottom = 144, 650, 936, 1135
	rows = [("角色", "需求", "下一步"), ("引薦", "說清楚", "安排認識"), ("客戶", "確認方向", "持續合作")]
	col_x = [left, 360, 620, right]
	row_h = (bottom - top) // len(rows)
	for row_index, row in enumerate(rows):
		y = top + row_index * row_h
		visible = _eoc((progress * len(rows) - row_index + 0.35))
		if visible <= 0:
			continue
		fill = PANEL_2 if row_index == 0 else PANEL
		draw.rounded_rectangle([left, y, right, y + row_h - 8], radius=12, fill=_alpha(fill, opacity * visible), outline=_alpha(TEAL if row_index == 0 else (74, 92, 94), opacity * visible), width=3)
		for col_index, label in enumerate(row):
			font = _font("H" if row_index == 0 else "B", 30 if row_index == 0 else 28)
			cx = (col_x[col_index] + col_x[col_index + 1]) / 2
			width = draw.textlength(label, font=font)
			draw.text((cx - width / 2, y + 47), label, font=font, fill=_alpha(WHITE, opacity * visible))


def _scene_loop(draw: ImageDraw.ImageDraw, progress: float, opacity: float) -> None:
	cx, cy = W // 2, 820
	box = [cx - 180, cy - 180, cx + 180, cy + 180]
	draw.arc(box, -80, 260, fill=_alpha(TEAL, opacity), width=24)
	draw.arc(box, 100, 440, fill=_alpha(GOLD, opacity), width=24)
	angle = math.radians(-80 + (340 * progress) % 360)
	point = (int(cx + 180 * math.cos(angle)), int(cy + 180 * math.sin(angle)))
	draw.ellipse([point[0] - 18, point[1] - 18, point[0] + 18, point[1] + 18], fill=_alpha(WHITE, opacity))
	font = _font("H", 52)
	label = "持續合作"
	width = draw.textlength(label, font=font)
	draw.text((cx - width / 2, cy - 32), label, font=font, fill=_alpha(WHITE, opacity))


SCENES = {
	"people": _scene_people,
	"network": _scene_network,
	"table": _scene_table,
	"funnel": _scene_funnel,
	"pipeline": _scene_pipeline,
	"loop": _scene_loop,
}


def render(lay: str, kind: str, params: dict, dur: float, outdir: Path, fps: int = 30) -> int:
	if lay != "V":
		raise ValueError("broll_adapter 目前只支援直式 V 畫布")
	outdir.mkdir(parents=True, exist_ok=True)
	scene = SCENES.get(str(params.get("scene", "network")), _scene_network)
	headline = str(params.get("headline", "這段重點"))
	body = str(params.get("body", ""))
	frame_count = int(dur * fps)
	for frame in range(frame_count):
		local = frame / fps
		intro = _eoc(local / 0.55)
		outro = _c01((dur - local) / 0.45)
		opacity = _c01(intro * outro)
		image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
		draw = ImageDraw.Draw(image)
		# 全幅深色情境卡，字幕會在 FFmpeg 最後一層疊回來，不會被 B-roll 蓋掉。
		draw.rectangle([0, 0, W, H], fill=_alpha(DARK, opacity))
		# 兩個緩慢移動的光暈，讓畫面不會像一張死圖。
		glow_x = int(160 + 760 * ((local / max(dur, 1.0)) % 1.0))
		draw.ellipse([glow_x - 330, 250, glow_x + 330, 910], fill=_alpha((18, 82, 78), opacity * 0.15))
		draw.rounded_rectangle([74, 230, 1006, 1375], radius=46, fill=_alpha(PANEL, opacity), outline=_alpha(TEAL, opacity * 0.72), width=5)
		label_font = _font("B", 28)
		draw.text((120, 286), "情境示範  ·  B-ROLL", font=label_font, fill=_alpha(TEAL, opacity))
		headline_lines, headline_font = _fit_headline(headline)
		_draw_lines(draw, headline_lines, W // 2, 350, headline_font, _alpha(WHITE, opacity), 10)
		scene(draw, _c01(local / max(dur, 1.0)), opacity)
		if body:
			_text_block(draw, body, W // 2, 1125, _font("B", 34), _alpha(MUTED, opacity), 760, 8)
		# 下方小進度線提供轉場感，但不搶字幕。
		progress = _c01(local / max(dur, 1.0))
		draw.rounded_rectangle([150, 1290, 930, 1300], radius=5, fill=_alpha((54, 75, 77), opacity),)
		draw.rounded_rectangle([150, 1290, 150 + int(780 * progress), 1300], radius=5, fill=_alpha(GOLD, opacity),)
		image.save(outdir / f"ov_{frame:04d}.png")
	return frame_count

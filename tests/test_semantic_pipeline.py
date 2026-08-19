import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_review  # noqa: E402
import broll_adapter  # noqa: E402
import render_semantic  # noqa: E402
import render_shorts  # noqa: E402
import select_short_segments  # noqa: E402
import semantic_edit  # noqa: E402
import talking_head_adapter  # noqa: E402
from subtitle_layout import mixed_text_tokens, split_subtitle_cue, visual_width, wrap_chinese, wrap_english  # noqa: E402


class SemanticPipelineTests(unittest.TestCase):
	def test_unsafe_drop_tokens_are_kept(self):
		words = [
			{"id": "0:0", "text": "嗯", "start": 0.0, "end": 0.2},
			{"id": "0:1", "text": "客戶", "start": 0.6, "end": 1.0},
			{"id": "0:2", "text": "這個", "start": 1.0, "end": 1.3},
		]
		result = {
			"cues": [
				{
					"word_ids": ["0:0", "0:1", "0:2"],
					"drop_word_ids": ["0:0", "0:1", "0:2"],
					"zh": "客戶這個",
					"en": "This client",
					"confidence": 0.8,
				}
			]
		}
		payload = semantic_edit.validate_and_normalise(result, words, 0.0, 2.0)
		self.assertEqual([item["text"] for item in payload["deletions"]], ["嗯"])
		self.assertEqual(payload["cues"][0]["drop_word_ids"], ["0:0"])

	def test_frame_alignment_keeps_audio_and_video_on_same_grid(self):
		cuts = [{"start": 0.42, "end": 0.58, "word_ids": ["0:0"], "text": "嗯"}]
		aligned = render_semantic.frame_align_intervals(cuts)
		self.assertEqual(aligned[0]["start"], 0.433333)
		self.assertEqual(aligned[0]["end"], 0.6)

	def test_output_time_subtracts_previous_cuts(self):
		cuts = [{"start": 1.0, "end": 1.5}]
		self.assertAlmostEqual(render_semantic.output_time(2.0, 0.0, cuts), 1.5)
		self.assertAlmostEqual(render_semantic.output_time(1.2, 0.0, cuts), 1.0)

	def test_manual_review_only_cuts_approved_words_or_sentences(self):
		edit = {
			"schema_version": 1,
			"words": [
				{"id": "0:0", "text": "嗯", "start": 0.0, "end": 0.2},
				{"id": "0:1", "text": "保留", "start": 0.3, "end": 0.8},
				{"id": "1:0", "text": "整句", "start": 1.2, "end": 1.8},
				{"id": "1:1", "text": "刪除", "start": 1.9, "end": 2.4},
			],
			"cues": [
				{"id": 1, "word_ids": ["0:0", "0:1"], "source_start": 0.0, "source_end": 0.8, "zh": "保留"},
				{"id": 2, "word_ids": ["1:0", "1:1"], "source_start": 1.2, "source_end": 2.4, "zh": "整句刪除"},
			],
			"deletions": [{"word_id": "0:0", "start": 0.0, "end": 0.2}],
		}
		reviewed = apply_review.apply_review(
			edit,
			{
				"kind": "awesome-janson-review",
				"approved_word_ids": ["0:0"],
				"approved_cue_ids": [2],
				"decision_by_cue": {"1": "filler", "2": "delete"},
				"subtitle_style": {"zh_font_size": 58, "en_font_size": 22, "show_english": False},
			},
		)
		cuts = render_semantic.build_intervals(reviewed, physical_cut=True)
		self.assertEqual([(cut["start"], cut["end"]) for cut in cuts], [(0.0, 0.2), (1.2, 2.4)])
		self.assertEqual(len(render_semantic.build_cues(reviewed, 0.0, cuts)), 1)
		self.assertEqual(reviewed["review"]["mode"], "manual-review")
		self.assertEqual(reviewed["subtitle_style"], {"zh_font_size": 58, "en_font_size": 22, "show_english": False})

	def test_mixed_subtitles_wrap_without_splitting_ascii_words(self):
		zh = wrap_chinese("大家最紅的黃仁勳，每年Computex一定要搬這些東西到Computex去。")
		en = wrap_english("The most popular speaker presents these examples at Computex every year.")
		self.assertIn("Computex", zh)
		self.assertLessEqual(max(visual_width(line, 34) for line in zh.split("\\N")), 1080)
		self.assertLessEqual(max(visual_width(line, 20, english=True) for line in en.split("\\N")), 1080)

	def test_short_selector_extends_comma_ending_to_complete_sentence(self):
		cues = [
			{"source_start": 10.0, "source_end": 12.0, "zh": "前面完整。"},
			{"source_start": 12.0, "source_end": 14.0, "zh": "我們要切出一條，"},
			{"source_start": 14.0, "source_end": 16.0, "zh": "不一樣的單。"},
		]
		self.assertEqual(select_short_segments.extend_to_natural_end(cues, 10.0, 14.0, 75.0), 16.0)

	def test_short_selector_recognises_sentence_end_before_closing_quote(self):
		for text in ("他說：「好。」", "（完整句。）"):
			cues = [
				{"source_start": 10.0, "source_end": 12.0, "zh": text},
				{"source_start": 12.0, "source_end": 14.0, "zh": "下一句。"},
			]
			self.assertEqual(select_short_segments.extend_to_natural_end(cues, 10.0, 12.0, 75.0), 12.0)

	def test_short_selector_does_not_stop_mid_cue_or_at_ascii_colon(self):
		terminal_cue = [{"source_start": 10.0, "source_end": 16.0, "zh": "完整句。"}]
		self.assertEqual(select_short_segments.extend_to_natural_end(terminal_cue, 10.0, 14.0, 75.0), 16.0)
		self.assertEqual(
			select_short_segments.extend_to_natural_end(terminal_cue, 10.0, 14.0, 75.0, limit_end=14.0),
			10.0,
		)
		colon_cues = [
			{"source_start": 10.0, "source_end": 12.0, "zh": "接下來:"},
			{"source_start": 12.0, "source_end": 14.0, "zh": "下一段。"},
		]
		self.assertEqual(select_short_segments.extend_to_natural_end(colon_cues, 10.0, 12.0, 75.0), 14.0)

	def test_shortening_keeps_unbroken_ascii_term(self):
		self.assertEqual(talking_head_adapter._shorten("PowerTeamSuperLongName", 14), "PowerTeamSuperLongName")
		self.assertEqual(talking_head_adapter._shorten("這是SEO/BNI/loader", 14), "這是…")

	def test_shortening_never_returns_a_fragmented_url(self):
		url = "https://example.com/path/to/resource?source=shorts&variant=tw"
		self.assertTrue(talking_head_adapter._shorten(url, 20).startswith("https://"))
		self.assertTrue(talking_head_adapter._shorten("請到 " + url, 20).startswith("https://"))

	def test_broll_headline_does_not_split_url_at_punctuation(self):
		url = "https://example.com/path/to/resource?source=shorts&variant=tw"
		lines, _ = broll_adapter._fit_headline(url)
		self.assertEqual(len(lines), 1)
		self.assertTrue(lines[0].startswith("https://"))
		self.assertNotEqual(lines[0], "https:…")

	def test_long_url_subtitle_stays_bounded_without_empty_cues(self):
		url = "https://" + "a" * 100 + ".example.com/path?source=shorts&variant=tw"
		for text in (url, "請看 " + url + "，了解詳情。"):
			parts = split_subtitle_cue({"start": 0.0, "end": 5.0, "zh": text, "en": ""})
			self.assertTrue(all(part["zh"] or part["en"] for part in parts))
			for part in parts:
				wrapped = wrap_chinese(part["zh"])
				self.assertLessEqual(max(visual_width(line, 50) for line in wrapped.split(r"\N")), 1080)

	def test_long_ascii_subtitle_keeps_terminal_punctuation_with_text(self):
		url = "https://" + "a" * 100 + ".example.com/path."
		parts = split_subtitle_cue({"start": 0.0, "end": 5.0, "zh": url, "en": ""})
		self.assertFalse(any(part["zh"] in {".", "。", ":", "："} for part in parts))
		self.assertTrue(parts[0]["zh"].endswith("."))

	def test_truncated_url_does_not_create_a_punctuation_only_line(self):
		text = "請看 https://" + "a" * 100 + ".example.com/path."
		lines = wrap_chinese(text).split(r"\N")
		self.assertFalse(any(line in {".", "。", ":", "："} for line in lines))
		self.assertTrue(any(line.endswith(".") for line in lines))

	def test_url_tokens_keep_parentheses_and_semicolon_parameters(self):
		for url in ("https://example.com/a(b)", "https://example.com/foo;param=bar"):
			self.assertEqual(mixed_text_tokens(url), [url])

	def test_stamp_font_fits_the_entrance_scale(self):
		from PIL import Image, ImageDraw

		ctx = talking_head_adapter.anim_lib.Ctx("V")
		draw = ImageDraw.Draw(Image.new("RGBA", (ctx.W, ctx.H)))
		scale = 1.9
		pad = ctx.s(56) * scale
		max_width = ctx.W - 2 * pad - ctx.s(56)
		label = "PowerTeamSuperLongName"
		font = talking_head_adapter.anim_lib._fit_stamp_font(draw, label, "B", int(ctx.s(40) * scale), max_width)
		self.assertLessEqual(draw.textlength(label, font=font), max_width)

	def test_short_selector_does_not_extend_across_long_silence(self):
		cues = [
			{"source_start": 10.0, "source_end": 12.0, "zh": "前半句，"},
			{"source_start": 22.0, "source_end": 24.0, "zh": "後半句。"},
		]
		self.assertEqual(select_short_segments.extend_to_natural_end(cues, 10.0, 12.0, 75.0), 12.0)

	def test_short_caption_keeps_url_as_a_single_protected_token(self):
		url = "https://example.com/path/to/resource?source=shorts&variant=tw"
		text = "前面" * 10 + "，" + url + "，" + "後面" * 20
		with self.assertRaisesRegex(ValueError, "安全標點"):
			render_shorts.fit_short_caption_lines(text)
		parts = render_shorts.split_short_text(text)
		self.assertTrue(any(url in part for part in parts))
		self.assertFalse(any(part.endswith("https:") or part.endswith("example.") for part in parts))

	def test_extreme_ascii_caption_uses_readable_safe_display_fallback(self):
		url = "https://" + "a" * 300 + ".example.com/path?source=shorts&variant=tw"
		for text, prefix in ((url, "https://"), ("A" * 300, "A")):
			lines, font_size = render_shorts.fit_short_caption_lines(text)
			self.assertGreaterEqual(font_size, render_shorts.SHORT_CAPTION_MIN_FONT_SIZE)
			self.assertEqual(len(lines), 1)
			self.assertTrue(lines[0].startswith(prefix))
			self.assertTrue(lines[0].endswith("…"))
			self.assertLessEqual(visual_width(lines[0], font_size), render_shorts.SHORT_CAPTION_WIDTH)

	def test_unpunctuated_short_caption_keeps_full_text_or_requires_review(self):
		readable = "這是一段沒有標點的完整口語意群請完整保留"
		lines, _ = render_shorts.fit_short_caption_lines(readable)
		self.assertEqual(lines, [readable])
		self.assertNotIn("…", lines[0])
		too_long = "這" * 40
		self.assertEqual(render_shorts.split_short_text(too_long), [too_long])
		with self.assertRaisesRegex(ValueError, "安全標點"):
			render_shorts.fit_short_caption_lines(too_long)

	def test_mixed_oversized_ascii_caption_requires_review_instead_of_dropping_speech(self):
		text = "請到 https://" + "a" * 100 + ".example.com/path 了解詳情"
		with self.assertRaisesRegex(ValueError, "安全標點"):
			render_shorts.fit_short_caption_lines(text)

	def test_shortening_bounds_extreme_ascii_term_without_empty_card(self):
		shortened = talking_head_adapter._shorten("A" * 100, 14)
		self.assertNotEqual(shortened, "…")
		self.assertTrue(shortened.endswith("…"))
		self.assertLessEqual(len(shortened), 30)

	def test_short_render_adds_tail_padding_before_fade(self):
		with tempfile.TemporaryDirectory() as directory:
			with patch.object(render_shorts.subprocess, "run") as run:
				render_shorts.render_segment(
					Path("source.mp4"),
					Path(directory) / "output.mp4",
					Path(directory) / "captions.ass",
					0.0,
					10.0,
					1.0,
					"editorial",
				)
			command = run.call_args.args[0]
			filter_complex = command[command.index("-filter_complex") + 1]
			audio_filter = command[command.index("-af") + 1]
			t_indices = [index for index, value in enumerate(command) if value == "-t"]
			self.assertIn("tpad=stop_mode=clone", filter_complex)
			self.assertIn("apad=pad_dur=", audio_filter)
			self.assertEqual(command[t_indices[-1] + 1], f"{10.0 + render_shorts.TAIL_PAD_SECONDS:.3f}")

	def test_short_caption_mapping_uses_segment_relative_time(self):
		captions = render_shorts.build_captions(
			{
				"cues": [
					{"source_start": 100.0, "source_end": 102.0, "zh": "第一句", "en": "First"},
					{"source_start": 104.0, "source_end": 106.0, "zh": "第二句", "en": "Second"},
				]
			},
			100.0,
			110.0,
			2.0,
		)
		self.assertEqual(captions[0]["start"], 0.0)
		self.assertGreater(captions[1]["start"], captions[0]["end"])

	def test_short_captions_merge_orphans_and_hide_english(self):
		captions = render_shorts.build_captions(
			{
				"cues": [
					{"source_start": 100.0, "source_end": 101.0, "zh": "這是一句話，我"},
					{"source_start": 101.0, "source_end": 101.4, "zh": "們測一下。", "en": "Let's test."},
					{"source_start": 102.0, "source_end": 102.2, "zh": "麼？", "en": "What?"},
				],
			},
			100.0,
			103.0,
			1.0,
		)
		self.assertTrue(any("我們測一下" in caption["zh"] for caption in captions))
		self.assertFalse(any(caption["en"] for caption in captions))
		self.assertFalse(any(len(caption["zh"]) <= 2 for caption in captions))

	def test_short_prompt_requires_chinese_only_complete_cues(self):
		prompt = semantic_edit.make_prompt(
			[{"id": "0:0", "start": 0.0, "end": 1.0, "text": "什麼"}],
			0.0,
			1.0,
			shorts=True,
		)
		self.assertIn("en 欄位一律輸出空字串", prompt)
		self.assertIn('"en":""', prompt)
		self.assertIn("禁止讓畫面只剩一個字", prompt)

	def test_talking_head_events_cover_timeline_and_use_existing_caption_text(self):
		events = talking_head_adapter.build_events(
			[
				{"start": 0.0, "end": 2.0, "zh": "一般引薦，不要捏造數字"},
				{"start": 2.0, "end": 5.0, "zh": "理想引薦與合作"},
				{"start": 5.0, "end": 8.0, "zh": "協力廠商與接水管"},
				{"start": 8.0, "end": 12.0, "zh": "夢幻引薦與長期合作"},
			],
			52.0,
			include_broll=True,
		)
		self.assertGreaterEqual(len(events), 5)
		self.assertEqual(events[0]["kind"], "broll")
		self.assertIn("checklist", [event["kind"] for event in events])
		self.assertIn("stamp", [event["kind"] for event in events])
		self.assertLessEqual(max(events[index + 1]["start"] - (events[index]["start"] + events[index]["duration"]) for index in range(len(events) - 1)), 3.0)
		self.assertIn("一般引薦", json.dumps(events, ensure_ascii=False))
		self.assertNotIn("30%", json.dumps(events, ensure_ascii=False))

	def test_short_ass_shrinks_long_text_before_forcing_line_break(self):
		with tempfile.TemporaryDirectory() as directory:
			output = Path(directory) / "long.ass"
			render_shorts.write_ass(
				[
					{
						"start": 0.0,
						"end": 4.0,
						"zh": "一般引薦，其實你在外面靠 SEO、靠你的廣告行銷，",
						"en": "",
					}
				],
				output,
				"測試標題",
				"editorial",
				4.0,
			)
			content = output.read_text(encoding="utf-8")
			self.assertIn(r"SEO、\N靠", content)
			self.assertIn(r"\fs", content)
			self.assertNotIn("English", content)

	def test_talking_head_ass_includes_optional_cta(self):
		with tempfile.TemporaryDirectory() as directory:
			output = Path(directory) / "test.ass"
			render_shorts.write_ass([], output, "測試標題", "editorial", 20.0, "追蹤剪神")
			content = output.read_text(encoding="utf-8")
			self.assertIn("Style: CTA", content)
			self.assertIn("追蹤剪神", content)

	def test_newline_heavy_model_cue_is_normalised_before_wrapping(self):
		parts = split_subtitle_cue(
			{
				"start": 0.0,
				"end": 5.0,
				"zh": "第一句\n第二句",
				"en": "First sentence,\nsecond sentence,\nthey would say,",
			}
		)
		for part in parts:
			self.assertLessEqual(len(wrap_chinese(part["zh"]).split("\\N")), 2)
			self.assertLessEqual(len(wrap_english(part["en"]).split("\\N")), 2)
		self.assertNotIn("\n", part["en"])

	def test_long_cue_is_split_to_at_most_two_lines_per_language(self):
		cue = {
			"start": 0.0,
			"end": 5.0,
			"zh": "大家最紅的黃仁勳、黃爸，每年Computex一定要搬這些東西到Computex去。",
			"en": "The most popular Jensen Huang, Huang-ba, every year at Computex, we have to move these things to Computex.",
		}
		parts = split_subtitle_cue(cue)
		self.assertGreaterEqual(len(parts), 1)
		for part in parts:
			self.assertLessEqual(len(wrap_chinese(part["zh"]).split("\\N")), 2)
			self.assertLessEqual(len(wrap_english(part["en"]).split("\\N")), 2)


if __name__ == "__main__":
	unittest.main()

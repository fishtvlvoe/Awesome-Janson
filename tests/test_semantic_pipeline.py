import io
import json
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_review  # noqa: E402
import broll_adapter  # noqa: E402
import fal_broll_provider  # noqa: E402
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

	def test_short_selector_extends_across_a_short_asr_gap(self):
		cues = [
			{"source_start": 10.0, "source_end": 12.0, "zh": "前半句，"},
			{"source_start": 12.3, "source_end": 14.0, "zh": "後半句。"},
		]
		self.assertEqual(select_short_segments.extend_to_natural_end(cues, 10.0, 12.2, 75.0), 14.0)

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

	def test_short_caption_keeps_closing_delimiter_with_previous_clause(self):
		text = "前" * 25 + "。』" + "後" * 25 + "，"
		parts = render_shorts.split_short_text(text)
		self.assertFalse(any(part == "』" for part in parts))
		self.assertTrue(any(part.endswith("。』") for part in parts))

	def test_short_caption_coalesces_safe_clauses_before_timing(self):
		text = "重點內容，" * 12
		parts = render_shorts.split_short_text(text)
		self.assertLess(len(parts), 12)
		captions = render_shorts.split_caption({"zh": text}, 0.0, 0.0, 5.4, 1.0)
		self.assertGreaterEqual(min(caption["end"] - caption["start"] for caption in captions), 1.0)

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

	def test_fal_config_reads_local_env_without_exposing_key(self):
		with tempfile.TemporaryDirectory() as directory:
			env_file = Path(directory) / "fal.env"
			env_file.write_text(
				"FAL_KEY=keep-this-local" + chr(10) + "AWJ_FAL_IMAGE_MODEL=fal-ai/nano-banana-2" + chr(10) + "UNRELATED_KEY=ignore-me" + chr(10),
				encoding="utf-8",
			)
			config = fal_broll_provider.resolve_fal_config(
				"image",
				allow_remote=True,
				env={},
				env_file=env_file,
			)
			self.assertEqual(config.model, "fal-ai/nano-banana-2")
			self.assertNotIn("keep-this-local", repr(config))
			self.assertEqual(config.input_overrides, {})
			override = fal_broll_provider.resolve_fal_config(
				"image",
				allow_remote=True,
				env={"FAL_API_KEY": "runtime-wins"},
				env_file=env_file,
			)
			self.assertEqual(override.api_key, "runtime-wins")

	def test_fal_requires_opt_in_and_video_model(self):
		with self.assertRaises(fal_broll_provider.FalBrollError) as disabled:
			fal_broll_provider.resolve_fal_config("image", allow_remote=False, env={"FAL_KEY": "local"})
		self.assertEqual(disabled.exception.reason, "remote-opt-in-required")
		with self.assertRaises(fal_broll_provider.FalBrollError) as missing_model:
			fal_broll_provider.resolve_fal_config("video", allow_remote=True, env={"FAL_KEY": "local"})
		self.assertEqual(missing_model.exception.reason, "fal-video-model-not-configured")

	def test_fal_queue_download_does_not_send_key_to_media_url(self):
		class FakeResponse:
			def __init__(self, body, headers=None):
				self.stream = io.BytesIO(body)
				self.headers = headers or {}

			def read(self, size=-1):
				return self.stream.read(size)

			def __enter__(self):
				return self

			def __exit__(self, *_args):
				return False

		with tempfile.TemporaryDirectory() as directory:
				image = Image.new("RGB", (32, 48), (10, 20, 30))
				buffer = io.BytesIO()
				image.save(buffer, format="PNG")
				png = buffer.getvalue()
				calls = []

				def fake_urlopen(request, timeout):
					calls.append((request.full_url, dict(request.header_items()), request.get_method()))
					if request.full_url.endswith("/status"):
						return FakeResponse(b'{"status":"COMPLETED"}')
					if request.full_url.endswith("/requests/request-123"):
						return FakeResponse(b'{"images":[{"url":"https://fal.media/files/generated.png?signature=temporary"}]}')
					if request.full_url.startswith("https://fal.media/"):
						return FakeResponse(png, {"Content-Length": str(len(png)), "Content-Type": "image/png"})
					return FakeResponse(b'{"request_id":"request-123"}')

				config = fal_broll_provider.FalConfig("image", "fal-ai/flux/schnell", "keep-this-local", timeout_seconds=10)
				with patch.object(fal_broll_provider, "urlopen", side_effect=fake_urlopen):
					generated = fal_broll_provider.generate_media(config, {"headline": "合作流程"}, 3.5, Path(directory) / "cache")
				self.assertTrue(generated.cache_path.is_file())
				self.assertEqual(generated.request_id, "request-123")
				queue_headers = calls[0][1]
				self.assertTrue(any(name.lower() == "authorization" and value == "Key keep-this-local" for name, value in queue_headers.items()))
				media_headers = next(headers for url, headers, _method in calls if url.startswith("https://fal.media/"))
				self.assertFalse(any(name.lower() == "authorization" for name in media_headers))
				self.assertNotIn("signature=temporary", repr(generated))
				self.assertNotIn("keep-this-local", repr(generated))

	def test_fal_cache_setup_failure_becomes_safe_fallback_error(self):
		with tempfile.TemporaryDirectory() as directory:
			cache_file = Path(directory) / "cache-file"
			cache_file.write_text("not a directory", encoding="utf-8")
			config = fal_broll_provider.FalConfig("image", "fal-ai/flux/schnell", "keep-this-local", timeout_seconds=10)
			with self.assertRaisesRegex(fal_broll_provider.FalBrollError, "fal-cache-unavailable"):
				fal_broll_provider.generate_media(config, {"headline": "合作流程"}, 3.0, cache_file)

	def test_fal_timeout_cancels_pending_queue_work(self):
		config = fal_broll_provider.FalConfig("image", "fal-ai/flux/schnell", "keep-this-local", timeout_seconds=10)
		calls = []

		def fake_json_request(method, url, **_kwargs):
			calls.append((method, url))
			if method == "POST":
				return {"request_id": "request-123"}
			if method == "PUT":
				return {"status": "CANCELLED"}
			return {"status": "IN_QUEUE"}

		with patch.object(fal_broll_provider, "_json_request", side_effect=fake_json_request):
			with patch.object(fal_broll_provider.time, "monotonic", side_effect=(0.0, 11.0)):
				with self.assertRaisesRegex(fal_broll_provider.FalBrollError, "fal-request-timeout"):
					fal_broll_provider._queue_result(config, {"prompt": "test"})
		self.assertIn(
			("PUT", "https://queue.fal.run/fal-ai/flux/schnell/requests/request-123/cancel"),
			calls,
		)

	def test_fal_decompression_bomb_becomes_safe_fallback_error(self):
		with patch.object(fal_broll_provider.Image, "open", side_effect=Image.DecompressionBombError("too many pixels")):
			with self.assertRaisesRegex(fal_broll_provider.FalBrollError, "fal-image-media-invalid"):
				fal_broll_provider._load_image(Path("untrusted-image.png"))

	def test_fal_decompression_bomb_warning_becomes_safe_fallback_error(self):
		def emit_warning(_path):
			warnings.warn("too many pixels", Image.DecompressionBombWarning)

		with patch.object(fal_broll_provider.Image, "open", side_effect=emit_warning):
			with self.assertRaisesRegex(fal_broll_provider.FalBrollError, "fal-image-media-invalid"):
				fal_broll_provider._load_image(Path("warning-image.png"))

	def test_fal_rejects_oversized_decoded_image_before_copying(self):
		class OversizedImage:
			width = 10_000
			height = 10_000

			def __enter__(self):
				return self

			def __exit__(self, *_args):
				return False

		with patch.object(fal_broll_provider.Image, "open", return_value=OversizedImage()):
			with self.assertRaisesRegex(fal_broll_provider.FalBrollError, "fal-image-media-too-large"):
				fal_broll_provider._load_image(Path("oversized-image.png"))

	def test_fal_video_frame_compositor_streams_source_images(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			paths = [root / "one.png", root / "two.png"]
			Image.new("RGB", (32, 48), (20, 40, 60)).save(paths[0])
			Image.new("RGB", (32, 48), (80, 100, 120)).save(paths[1])
			with patch.object(fal_broll_provider, "_load_image", wraps=fal_broll_provider._load_image) as load_image:
				count = fal_broll_provider._write_composed_frames(paths, 1.0, root / "frames", 3, cache_sources=False)
			self.assertEqual(count, 3)
			self.assertEqual(load_image.call_count, 3)

	def test_fal_image_frames_and_remote_failure_fallback_are_manifest_safe(self):
		with tempfile.TemporaryDirectory() as directory:
				directory_path = Path(directory)
				media_path = directory_path / "source.png"
				Image.new("RGB", (180, 320), (30, 80, 120)).save(media_path)
				config = fal_broll_provider.FalConfig("image", "fal-ai/flux/schnell", "keep-this-local", timeout_seconds=10)
				generated = fal_broll_provider.GeneratedMedia("image", config.model, media_path, "request-123", True)
				cache_dir = directory_path / "final-output" / ".fal-cache"
				with patch.object(fal_broll_provider, "generate_media", return_value=generated) as generate_media:
					metadata = fal_broll_provider.render_fal_broll(
						config,
						{"headline": "合作流程"},
						1.0,
						directory_path / "frames",
						fps=2,
						cache_dir=cache_dir,
					)
				self.assertEqual(generate_media.call_args.args[3], cache_dir)
				self.assertEqual(metadata["provider"], "fal-image")
				self.assertTrue((directory_path / "frames" / "ov_0000.png").is_file())
				self.assertNotIn("keep-this-local", json.dumps(metadata))

				events = [{"kind": "broll", "start": 1.0, "duration": 2.0, "params": {"headline": "合作流程"}}]
				with patch.object(fal_broll_provider, "render_fal_broll", return_value={"provider": "fal-image"}) as remote_render:
					remote = talking_head_adapter.render_events(
						events,
						directory_path / "remote",
						broll_provider="fal-image",
						fal_config=config,
						fal_cache_dir=cache_dir,
					)
				self.assertEqual(remote[0]["provider"], "fal-image")
				self.assertEqual(remote_render.call_args.kwargs["cache_dir"], cache_dir)

				with patch.object(fal_broll_provider, "render_fal_broll", side_effect=fal_broll_provider.FalBrollError("fal-network-error")):
					with patch.object(broll_adapter, "render", return_value=60) as local_render:
						fallback = talking_head_adapter.render_events(
							events,
							directory_path / "fallback",
							broll_provider="fal-image",
							fal_config=config,
						)
				self.assertEqual(fallback[0]["provider"], "local")
				self.assertEqual(fallback[0]["fallback_reason"], "fal-network-error")
				self.assertNotIn("keep-this-local", json.dumps(fallback, ensure_ascii=False))
				local_render.assert_called_once()


if __name__ == "__main__":
	unittest.main()

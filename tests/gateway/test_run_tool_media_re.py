r"""Tests for the _TOOL_MEDIA_RE pattern in gateway/run.py.

Issue #34632: _TOOL_MEDIA_RE used (?:/|~\/) to anchor paths, which only matched
Unix-style absolute and home-relative paths. Windows absolute paths
(C:\\Users\\..., D:/...) were silently ignored, causing MEDIA directive delivery
to fail on Windows.

The pattern is IMPORTED from gateway/run.py — an earlier revision of this file
reconstructed it by hand, so the tests kept passing while the production regex
drifted (the aac/amr TTS gap below was invisible to them). Alongside the
behavioral cases, the relationship test ties the regex to the extension
vocabulary its gated producers actually emit.
"""

import pytest

from gateway.run import _TOOL_MEDIA_RE, _collect_auto_append_media_tags
from tools.tts_command_provider import COMMAND_TTS_OUTPUT_FORMATS


class TestToolMediaReWindowsPaths:
    """Issue #34632: _TOOL_MEDIA_RE must match Windows absolute paths."""

    @pytest.mark.parametrize("media_tag, expected_path", [
        # Windows backslash paths
        ("MEDIA:C:\\Users\\test\\image.png", "C:\\Users\\test\\image.png"),
        ("MEDIA:D:\\data\\report.pdf", "D:\\data\\report.pdf"),
        ("MEDIA:E:\\Photos\\vacation.jpg", "E:\\Photos\\vacation.jpg"),
        # Windows forward-slash paths
        ("MEDIA:C:/Users/test/image.png", "C:/Users/test/image.png"),
        ("MEDIA:D:/data/report.pdf", "D:/data/report.pdf"),
        # Mixed separators
        ("MEDIA:C:\\Users/test\\image.webp", "C:\\Users/test\\image.webp"),
        # Various extensions
        ("MEDIA:F:\\videos\\clip.mp4", "F:\\videos\\clip.mp4"),
        ("MEDIA:G:\\audio\\song.mp3", "G:\\audio\\song.mp3"),
        ("MEDIA:H:\\docs\\sheet.xlsx", "H:\\docs\\sheet.xlsx"),
        ("MEDIA:Z:\\archive\\backup.zip", "Z:\\archive\\backup.zip"),
    ])
    def test_windows_paths_match(self, media_tag, expected_path):
        """Windows absolute paths with drive letters are matched."""
        match = _TOOL_MEDIA_RE.search(media_tag)
        assert match is not None, f"Should match: {media_tag}"
        assert match.group(1) == expected_path

    @pytest.mark.parametrize("media_tag", [
        "MEDIA:C:\\path\\file.jpeg",
        "MEDIA:C:\\path\\file.JPG",
        "MEDIA:C:\\path\\file.GIF",
        "MEDIA:C:\\path\\file.MP4",
    ])
    def test_case_insensitive_extensions(self, media_tag):
        """File extensions are matched case-insensitively."""
        match = _TOOL_MEDIA_RE.search(media_tag)
        assert match is not None, f"Should match: {media_tag}"


class TestToolMediaReCoversProducerFormats:
    """The auto-append collector only appends tags this regex accepts, so it must
    recognize every extension its gated producers can emit. text_to_speech emits
    whatever ``format``/``output_format`` tts_command_provider validates — aac and
    amr included — and a miss means the synthesis succeeds but the user receives
    no audio at all."""

    @pytest.mark.parametrize("fmt", sorted(COMMAND_TTS_OUTPUT_FORMATS))
    def test_every_tts_output_format_matches(self, fmt):
        assert _TOOL_MEDIA_RE.fullmatch(f"MEDIA:/home/u/.hermes/audio_cache/tts_1.{fmt}"), (
            f"TTS output format .{fmt} is dropped by the auto-append collector"
        )

    def test_aac_tts_result_is_collected(self):
        """End-to-end: a successful text_to_speech tool result in .aac must yield an
        auto-appended MEDIA tag (and keep its voice directive) — the regex alone is
        not the delivery path, the collector is."""
        messages = [
            {"role": "assistant", "content": None,
             "tool_calls": [{"id": "c1", "function": {"name": "text_to_speech"}}]},
            {"role": "tool", "tool_call_id": "c1",
             "content": "[[audio_as_voice]]\nMEDIA:/root/.hermes/audio_cache/tts_20260101.aac"},
        ]
        tags, voice = _collect_auto_append_media_tags(messages)
        assert tags == ["MEDIA:/root/.hermes/audio_cache/tts_20260101.aac"]
        assert voice is True

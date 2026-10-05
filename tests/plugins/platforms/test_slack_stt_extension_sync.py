"""The Slack adapter's STT extension list must never lag the transcription backend.

``plugins/platforms/slack/adapter.py::_SLACK_STT_SUPPORTED_EXTS`` is a hand-copy of
``tools.transcription_common.SUPPORTED_FORMATS``, kept in sync by a comment. Comments do
not fail tests, and the copy had drifted: ``.oga``, ``.opus`` and ``.caf`` were missing.

The effect is not a loud rejection — ``_resolve_slack_audio_ext`` falls back to a mimetype
table — so an inbound ``.opus`` voice clip (the dominant chat audio format) lost the
extension it arrived with and was relabelled from whatever Slack reported, which the
adapter's own docstring warns is wrong for some containers.

Contract: the Slack set may be STRICTER-independent (it may add extensions), but never
narrower than the backend — every format the STT layer accepts must be trusted by name
when it arrives. Asserting the RELATIONSHIP is what stops the next upstream addition from
silently dropping a format; asserting the literal list would only freeze today's values.
"""

from plugins.platforms.slack import adapter as slack_adapter
from tools.transcription_common import SUPPORTED_FORMATS


def test_slack_stt_extensions_are_never_narrower_than_the_stt_backend():
    missing = sorted(SUPPORTED_FORMATS - set(slack_adapter._SLACK_STT_SUPPORTED_EXTS))
    assert not missing, (
        f"the Slack adapter would relabel inbound {missing} audio from its mimetype "
        f"instead of trusting the filename extension, because they are absent from "
        f"_SLACK_STT_SUPPORTED_EXTS. Add them."
    )


def test_opus_voice_clip_keeps_its_extension():
    """The user-visible half: a ``.opus`` clip is cached as ``.opus``, not relabelled."""
    clip = {"name": "audio_message.opus", "subtype": "slack_audio"}
    assert slack_adapter._resolve_slack_audio_ext(clip, "audio/ogg") == ".opus"

"""Regression tests for the experimental macOS TTS baseline."""

import subprocess
from pathlib import Path

import pytest

from atosaac_virtual_partner.tts import MacOSSaySynthesizer, SpeechSynthesisError


class RecordingRunner:
    def __init__(self) -> None:
        self.command: list[str] | None = None
        self.options: dict[str, object] = {}

    def __call__(self, command, **options):
        self.command = list(command)
        self.options = options
        return subprocess.CompletedProcess(command, 0, "", "")


def test_macos_synthesizer_uses_stdin_and_writes_requested_audio(tmp_path) -> None:
    runner = RecordingRunner()
    executable = tmp_path / "say"
    executable.touch()
    output = tmp_path / "audio" / "hello.aiff"
    synthesizer = MacOSSaySynthesizer(
        voice="Tingting",
        rate=190,
        executable=executable,
        runner=runner,
    )

    result = synthesizer.synthesize(" 你好，世界。 ", output)

    assert result == output.resolve()
    assert runner.command == [
        str(executable),
        "-v",
        "Tingting",
        "-r",
        "190",
        "-o",
        str(output.resolve()),
        "-f",
        "-",
    ]
    assert runner.options["input"] == "你好，世界。"
    assert runner.options["check"] is True


def test_macos_synthesizer_can_play_without_creating_an_output_path(tmp_path) -> None:
    runner = RecordingRunner()
    executable = tmp_path / "say"
    executable.touch()
    synthesizer = MacOSSaySynthesizer(executable=executable, runner=runner)

    assert synthesizer.synthesize("直接播放") is None
    assert "-o" not in (runner.command or [])


@pytest.mark.parametrize("text", ["", "   "])
def test_macos_synthesizer_rejects_empty_text(tmp_path, text: str) -> None:
    executable = tmp_path / "say"
    executable.touch()
    synthesizer = MacOSSaySynthesizer(executable=executable)

    with pytest.raises(SpeechSynthesisError, match="不能为空"):
        synthesizer.synthesize(text)


def test_macos_synthesizer_rejects_unsupported_output_format(tmp_path) -> None:
    executable = tmp_path / "say"
    executable.touch()
    synthesizer = MacOSSaySynthesizer(executable=executable)

    with pytest.raises(SpeechSynthesisError, match=r"\.aiff"):
        synthesizer.synthesize("你好", tmp_path / "voice.mp3")


def test_macos_synthesizer_surfaces_command_failure(tmp_path) -> None:
    executable = tmp_path / "say"
    executable.touch()

    def fail(command, **options):
        del options
        raise subprocess.CalledProcessError(1, command, stderr="找不到指定音色")

    synthesizer = MacOSSaySynthesizer(executable=executable, runner=fail)

    with pytest.raises(SpeechSynthesisError, match="找不到指定音色"):
        synthesizer.synthesize("你好")

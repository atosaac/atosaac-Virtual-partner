"""Experimental TTS baseline; not the final voice or training implementation.

This module exists to test a replaceable text-to-audio boundary with macOS
system speech. It does not train, clone, or automatically voice chat replies.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


DEFAULT_MACOS_VOICE = "Tingting"
DEFAULT_SPEECH_RATE = 190
MAX_SPEECH_CHARACTERS = 5000


class SpeechSynthesisError(RuntimeError):
    """Raised when a TTS provider cannot synthesize the requested speech."""


class SpeechSynthesizer(Protocol):
    """Define the replaceable text-to-speech boundary used by the application."""

    def synthesize(self, text: str, output_path: Path | None = None) -> Path | None:
        """Speak text immediately or save it to an audio file."""
        ...


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


class MacOSSaySynthesizer:
    """Use macOS' built-in speech engine as a dependency-free TTS baseline."""

    def __init__(
        self,
        *,
        voice: str = DEFAULT_MACOS_VOICE,
        rate: int = DEFAULT_SPEECH_RATE,
        executable: Path = Path("/usr/bin/say"),
        runner: RunCommand | None = None,
    ) -> None:
        clean_voice = voice.strip()
        if not clean_voice:
            raise SpeechSynthesisError("语音名称不能为空")
        if not 80 <= rate <= 500:
            raise SpeechSynthesisError("语速必须在 80 到 500 之间")
        self.voice = clean_voice
        self.rate = rate
        self.executable = executable
        self._runner = runner or subprocess.run

    def synthesize(self, text: str, output_path: Path | None = None) -> Path | None:
        clean_text = text.strip()
        if not clean_text:
            raise SpeechSynthesisError("要朗读的文字不能为空")
        if len(clean_text) > MAX_SPEECH_CHARACTERS:
            raise SpeechSynthesisError(
                f"单次朗读不能超过 {MAX_SPEECH_CHARACTERS} 个字符"
            )
        if not self.executable.is_file():
            raise SpeechSynthesisError("找不到 macOS 系统语音命令 /usr/bin/say")

        target = self._prepare_output_path(output_path)
        command = [
            str(self.executable),
            "-v",
            self.voice,
            "-r",
            str(self.rate),
        ]
        if target is not None:
            command.extend(["-o", str(target)])
        command.extend(["-f", "-"])
        try:
            self._runner(
                command,
                input=clean_text,
                text=True,
                capture_output=True,
                check=True,
            )
        except FileNotFoundError as exc:
            raise SpeechSynthesisError("macOS 系统语音命令不可用") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or "").strip()
            message = detail or "macOS 系统语音合成失败"
            raise SpeechSynthesisError(message) from exc
        return target

    @staticmethod
    def _prepare_output_path(output_path: Path | None) -> Path | None:
        if output_path is None:
            return None
        target = output_path.expanduser().resolve()
        if target.suffix.casefold() not in {".aif", ".aiff", ".aifc", ".caf"}:
            raise SpeechSynthesisError("系统语音输出请使用 .aiff、.aif、.aifc 或 .caf")
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

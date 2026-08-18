import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


DEFAULT_CHARACTER_NAME = "atosaac"
DEFAULT_CHARACTER_VERSION = "0.27"
DEFAULT_CHARACTER_FILENAME = "atosaac_v0.27.md"
_VERSIONED_HEADING = re.compile(
    r"^#\s+(?P<name>.+?)\s+v(?P<version>[0-9][0-9A-Za-z._-]*)\s*$",
    re.MULTILINE,
)


class CharacterLoadError(ValueError):
    """Raised when a character profile cannot be loaded."""


@dataclass(frozen=True, slots=True)
class CharacterProfile:
    """An immutable, versioned set of character instructions."""

    name: str
    version: str
    instructions: str
    source: str


def _validate_instructions(instructions: str, source: str) -> str:
    normalized = instructions.strip()
    if not normalized:
        raise CharacterLoadError(f"Character file is empty: {source}")
    return normalized


def load_default_character() -> CharacterProfile:
    """Load the built-in reviewed atosaac profile."""
    resource = files("atosaac_virtual_partner.characters").joinpath(
        DEFAULT_CHARACTER_FILENAME
    )
    instructions = _validate_instructions(
        resource.read_text(encoding="utf-8"),
        DEFAULT_CHARACTER_FILENAME,
    )
    return CharacterProfile(
        name=DEFAULT_CHARACTER_NAME,
        version=DEFAULT_CHARACTER_VERSION,
        instructions=instructions,
        source=f"builtin:{DEFAULT_CHARACTER_FILENAME}",
    )


def load_character_file(path: str | Path) -> CharacterProfile:
    """Load an external Markdown character profile."""
    character_path = Path(path).expanduser()
    try:
        raw_instructions = character_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CharacterLoadError(
            f"Cannot read character file '{character_path}': {exc.strerror or exc}"
        ) from exc

    instructions = _validate_instructions(raw_instructions, str(character_path))
    heading = _VERSIONED_HEADING.search(instructions)
    name = heading.group("name") if heading else character_path.stem
    version = heading.group("version") if heading else "external"
    return CharacterProfile(
        name=name,
        version=version,
        instructions=instructions,
        source=str(character_path),
    )


def load_character(path: str | Path | None = None) -> CharacterProfile:
    """Load an external profile when supplied, otherwise use the built-in one."""
    if path is None:
        return load_default_character()
    return load_character_file(path)

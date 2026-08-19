import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


DEFAULT_MEMORY_DATABASE_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "atosaac-virtual-partner"
    / "memory.sqlite3"
)
MAX_MEMORY_CHARACTERS = 300
MAX_LIST_LIMIT = 1_000


class MemoryStoreError(RuntimeError):
    """Report a local memory storage failure without leaking SQL details."""


class DuplicateMemoryError(MemoryStoreError):
    """Report an attempt to save the same normalized memory twice."""

    def __init__(self, existing_id: int) -> None:
        self.existing_id = existing_id
        super().__init__(f"Memory already exists as #{existing_id}")


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One explicit, user-reviewable long-term memory."""

    id: int
    content: str
    created_at: datetime


class MemoryStore(Protocol):
    """Persist explicit memories behind a replaceable storage boundary."""

    def add(self, content: str) -> MemoryRecord: ...

    def list_recent(self, limit: int = 50) -> tuple[MemoryRecord, ...]: ...

    def delete(self, memory_id: int) -> bool: ...

    def clear(self) -> int: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_content(content: str) -> tuple[str, str]:
    if not isinstance(content, str):
        raise ValueError("Memory content must be text")
    normalized_content = " ".join(content.split())
    if not normalized_content:
        raise ValueError("Memory content cannot be empty")
    if len(normalized_content) > MAX_MEMORY_CHARACTERS:
        raise ValueError(
            f"Memory content cannot exceed {MAX_MEMORY_CHARACTERS} characters"
        )
    return normalized_content, normalized_content.casefold()


def _validate_positive_integer(value: int, field: str, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    if value <= 0:
        raise ValueError(f"{field} must be greater than zero")
    if value > maximum:
        raise ValueError(f"{field} cannot exceed {maximum}")


class SQLiteMemoryStore:
    """Store explicit memories in a private local SQLite database."""

    def __init__(
        self,
        database_path: Path,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.database_path = Path(database_path).expanduser()
        self._clock = clock

    def _connect(self) -> sqlite3.Connection:
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            database_existed = self.database_path.exists()
            connection = sqlite3.connect(self.database_path, timeout=5.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA secure_delete = ON")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    normalized_content TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
            if not database_existed:
                os.chmod(self.database_path, 0o600)
            return connection
        except (OSError, sqlite3.Error) as exc:
            raise MemoryStoreError("Cannot open the local memory database") from exc

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> MemoryRecord:
        try:
            return MemoryRecord(
                id=int(row["id"]),
                content=str(row["content"]),
                created_at=datetime.fromisoformat(str(row["created_at"])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MemoryStoreError("Local memory data is invalid") from exc

    def add(self, content: str) -> MemoryRecord:
        normalized_content, deduplication_key = _normalize_content(content)
        created_at = self._clock()
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("Memory clock must return a timezone-aware datetime")

        connection = self._connect()
        try:
            cursor = connection.execute(
                """
                INSERT INTO memories (content, normalized_content, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    normalized_content,
                    deduplication_key,
                    created_at.astimezone(timezone.utc).isoformat(),
                ),
            )
            connection.commit()
            memory_id = cursor.lastrowid
            if memory_id is None:
                raise MemoryStoreError("Local memory did not return an identifier")
            return MemoryRecord(memory_id, normalized_content, created_at)
        except sqlite3.IntegrityError as exc:
            row = connection.execute(
                "SELECT id FROM memories WHERE normalized_content = ?",
                (deduplication_key,),
            ).fetchone()
            if row is None:
                raise MemoryStoreError("Cannot save the local memory") from exc
            raise DuplicateMemoryError(int(row["id"])) from exc
        except sqlite3.Error as exc:
            raise MemoryStoreError("Cannot save the local memory") from exc
        finally:
            connection.close()

    def list_recent(self, limit: int = 50) -> tuple[MemoryRecord, ...]:
        _validate_positive_integer(limit, "Memory list limit", MAX_LIST_LIMIT)
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT id, content, created_at
                FROM memories
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return tuple(self._record_from_row(row) for row in rows)
        except sqlite3.Error as exc:
            raise MemoryStoreError("Cannot read the local memory database") from exc
        finally:
            connection.close()

    def delete(self, memory_id: int) -> bool:
        _validate_positive_integer(memory_id, "Memory id", 2**63 - 1)
        connection = self._connect()
        try:
            cursor = connection.execute(
                "DELETE FROM memories WHERE id = ?",
                (memory_id,),
            )
            connection.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise MemoryStoreError("Cannot delete the local memory") from exc
        finally:
            connection.close()

    def clear(self) -> int:
        connection = self._connect()
        try:
            cursor = connection.execute("DELETE FROM memories")
            connection.commit()
            connection.execute("VACUUM")
            return max(0, cursor.rowcount)
        except sqlite3.Error as exc:
            raise MemoryStoreError("Cannot clear the local memory database") from exc
        finally:
            connection.close()

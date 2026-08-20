import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
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


class MemorySource(StrEnum):
    """Describe how a durable memory entered the store."""

    EXPLICIT = "explicit"
    AUTOMATIC = "automatic"


class MemoryWriteAction(StrEnum):
    """Describe the observable result of one keyed memory write."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One user-reviewable local long-term memory."""

    id: int
    content: str
    created_at: datetime
    updated_at: datetime
    source: MemorySource
    memory_key: str | None


@dataclass(frozen=True, slots=True)
class MemoryWriteResult:
    """Return one record together with its create/update outcome."""

    record: MemoryRecord
    action: MemoryWriteAction


class MemoryStore(Protocol):
    """Persist local memories behind a replaceable storage boundary."""

    def add(self, content: str) -> MemoryRecord: ...

    def remember(
        self,
        content: str,
        memory_key: str,
        source: MemorySource = MemorySource.AUTOMATIC,
    ) -> MemoryWriteResult: ...

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


def _normalize_memory_key(memory_key: str) -> str:
    if not isinstance(memory_key, str):
        raise ValueError("Memory key must be text")
    normalized_key = memory_key.strip().casefold()
    if not normalized_key:
        raise ValueError("Memory key cannot be empty")
    if len(normalized_key) > 120:
        raise ValueError("Memory key cannot exceed 120 characters")
    if not all(
        character.isalnum() or character in {":", "_", "-"}
        for character in normalized_key
    ):
        raise ValueError("Memory key contains unsupported characters")
    return normalized_key


def _validate_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Memory clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc)


class SQLiteMemoryStore:
    """Store reviewable memories in a private local SQLite database."""

    def __init__(
        self,
        database_path: Path,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.database_path = Path(database_path).expanduser()
        self._clock = clock

    def _connect(self) -> sqlite3.Connection:
        connection: sqlite3.Connection | None = None
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
                    memory_key TEXT,
                    source TEXT NOT NULL DEFAULT 'explicit',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(memories)")
            }
            if "memory_key" not in columns:
                connection.execute("ALTER TABLE memories ADD COLUMN memory_key TEXT")
            if "source" not in columns:
                connection.execute(
                    "ALTER TABLE memories ADD COLUMN source TEXT NOT NULL "
                    "DEFAULT 'explicit'"
                )
            if "updated_at" not in columns:
                connection.execute("ALTER TABLE memories ADD COLUMN updated_at TEXT")
            connection.execute(
                "UPDATE memories SET updated_at = created_at WHERE updated_at IS NULL"
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS memories_memory_key_unique
                ON memories(memory_key)
                WHERE memory_key IS NOT NULL
                """
            )
            connection.execute("PRAGMA user_version = 2")
            connection.commit()
            if not database_existed:
                os.chmod(self.database_path, 0o600)
            return connection
        except (OSError, sqlite3.Error) as exc:
            if connection is not None:
                connection.close()
            raise MemoryStoreError("Cannot open the local memory database") from exc

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> MemoryRecord:
        try:
            return MemoryRecord(
                id=int(row["id"]),
                content=str(row["content"]),
                created_at=datetime.fromisoformat(str(row["created_at"])),
                updated_at=datetime.fromisoformat(str(row["updated_at"])),
                source=MemorySource(str(row["source"])),
                memory_key=(
                    None if row["memory_key"] is None else str(row["memory_key"])
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MemoryStoreError("Local memory data is invalid") from exc

    def add(self, content: str) -> MemoryRecord:
        normalized_content, deduplication_key = _normalize_content(content)
        created_at = _validate_timestamp(self._clock())

        connection = self._connect()
        try:
            cursor = connection.execute(
                """
                INSERT INTO memories (
                    content,
                    normalized_content,
                    memory_key,
                    source,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, NULL, ?, ?, ?)
                """,
                (
                    normalized_content,
                    deduplication_key,
                    MemorySource.EXPLICIT.value,
                    created_at.isoformat(),
                    created_at.isoformat(),
                ),
            )
            connection.commit()
            memory_id = cursor.lastrowid
            if memory_id is None:
                raise MemoryStoreError("Local memory did not return an identifier")
            return MemoryRecord(
                id=memory_id,
                content=normalized_content,
                created_at=created_at,
                updated_at=created_at,
                source=MemorySource.EXPLICIT,
                memory_key=None,
            )
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

    def remember(
        self,
        content: str,
        memory_key: str,
        source: MemorySource = MemorySource.AUTOMATIC,
    ) -> MemoryWriteResult:
        normalized_content, deduplication_key = _normalize_content(content)
        normalized_key = _normalize_memory_key(memory_key)
        if not isinstance(source, MemorySource):
            raise ValueError("Memory source is invalid")
        updated_at = _validate_timestamp(self._clock())

        connection = self._connect()
        try:
            existing = connection.execute(
                """
                SELECT id, content, memory_key, source, created_at, updated_at,
                       normalized_content
                FROM memories
                WHERE memory_key = ?
                """,
                (normalized_key,),
            ).fetchone()
            if existing is not None:
                if str(existing["normalized_content"]) == deduplication_key:
                    return MemoryWriteResult(
                        self._record_from_row(existing),
                        MemoryWriteAction.UNCHANGED,
                    )
                connection.execute(
                    """
                    UPDATE memories
                    SET content = ?, normalized_content = ?, source = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        normalized_content,
                        deduplication_key,
                        source.value,
                        updated_at.isoformat(),
                        int(existing["id"]),
                    ),
                )
                connection.commit()
                updated = connection.execute(
                    """
                    SELECT id, content, memory_key, source, created_at, updated_at
                    FROM memories
                    WHERE id = ?
                    """,
                    (int(existing["id"]),),
                ).fetchone()
                if updated is None:
                    raise MemoryStoreError("Updated memory could not be read")
                return MemoryWriteResult(
                    self._record_from_row(updated),
                    MemoryWriteAction.UPDATED,
                )

            duplicate = connection.execute(
                """
                SELECT id, content, memory_key, source, created_at, updated_at
                FROM memories
                WHERE normalized_content = ?
                """,
                (deduplication_key,),
            ).fetchone()
            if duplicate is not None:
                if duplicate["memory_key"] is None:
                    connection.execute(
                        "UPDATE memories SET memory_key = ? WHERE id = ?",
                        (normalized_key, int(duplicate["id"])),
                    )
                    connection.commit()
                    duplicate = connection.execute(
                        """
                        SELECT id, content, memory_key, source, created_at, updated_at
                        FROM memories
                        WHERE id = ?
                        """,
                        (int(duplicate["id"]),),
                    ).fetchone()
                    if duplicate is None:
                        raise MemoryStoreError("Linked memory could not be read")
                return MemoryWriteResult(
                    self._record_from_row(duplicate),
                    MemoryWriteAction.UNCHANGED,
                )

            cursor = connection.execute(
                """
                INSERT INTO memories (
                    content,
                    normalized_content,
                    memory_key,
                    source,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_content,
                    deduplication_key,
                    normalized_key,
                    source.value,
                    updated_at.isoformat(),
                    updated_at.isoformat(),
                ),
            )
            connection.commit()
            memory_id = cursor.lastrowid
            if memory_id is None:
                raise MemoryStoreError("Local memory did not return an identifier")
            return MemoryWriteResult(
                MemoryRecord(
                    id=memory_id,
                    content=normalized_content,
                    created_at=updated_at,
                    updated_at=updated_at,
                    source=source,
                    memory_key=normalized_key,
                ),
                MemoryWriteAction.CREATED,
            )
        except sqlite3.IntegrityError as exc:
            raise MemoryStoreError("Cannot update the local memory") from exc
        except sqlite3.Error as exc:
            raise MemoryStoreError("Cannot update the local memory") from exc
        finally:
            connection.close()

    def list_recent(self, limit: int = 50) -> tuple[MemoryRecord, ...]:
        _validate_positive_integer(limit, "Memory list limit", MAX_LIST_LIMIT)
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT id, content, memory_key, source, created_at, updated_at
                FROM memories
                ORDER BY updated_at DESC, id DESC
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

"""SQLite storage for electricity events."""

import aiosqlite
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EventRecord:
    """A single electricity event record."""
    id: int
    timestamp: datetime
    status: str  # "ON", "OFF"
    previous_status: Optional[str]  # "ON", "OFF", or None
    duration: Optional[str]  # Human-readable duration string


class EventStore:
    """Manages SQLite storage for electricity status events."""

    def __init__(self, db_path: str = "./data/electricity.db"):
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize the database and create tables if needed."""
        path = Path(self._db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                previous_status TEXT,
                duration TEXT
            )
        """)
        await self._db.commit()

        logger.info("Event store initialized at %s", self._db_path)

    async def add_event(self, timestamp: datetime, status: str,
                        previous_status: Optional[str] = None,
                        duration: Optional[str] = None):
        """Add a new event record."""
        await self._db.execute(
            "INSERT INTO events (timestamp, status, previous_status, duration) VALUES (?, ?, ?, ?)",
            (timestamp.isoformat(), status, previous_status, duration)
        )
        await self._db.commit()

    async def get_events(self, limit: int = 50) -> List[EventRecord]:
        """Get recent events in reverse chronological order."""
        cursor = await self._db.execute(
            "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [
            EventRecord(
                id=row["id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                status=row["status"],
                previous_status=row["previous_status"],
                duration=row["duration"]
            )
            for row in rows
        ]

    async def get_events_since(self, since: datetime, limit: int = 50) -> List[EventRecord]:
        """Get events since a specific timestamp."""
        cursor = await self._db.execute(
            "SELECT * FROM events WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?",
            (since.isoformat(), limit)
        )
        rows = await cursor.fetchall()
        return [
            EventRecord(
                id=row["id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                status=row["status"],
                previous_status=row["previous_status"],
                duration=row["duration"]
            )
            for row in rows
        ]

    async def purge_old_events(self, days: int = 3) -> int:
        """Remove events older than the specified number of days.

        Returns:
            Number of events purged.
        """
        cutoff = datetime.now() - timedelta(days=days)
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM events WHERE timestamp < ?",
            (cutoff.isoformat(),)
        )
        count_row = await cursor.fetchone()
        count = count_row[0] if count_row else 0

        if count > 0:
            await self._db.execute(
                "DELETE FROM events WHERE timestamp < ?",
                (cutoff.isoformat(),)
            )
            await self._db.commit()
            logger.info("Purged %d events older than %d days", count, days)

        return count

    async def clear_all_events(self) -> int:
        """Clear all events. Returns the number of events cleared."""
        cursor = await self._db.execute("SELECT COUNT(*) FROM events")
        count_row = await cursor.fetchone()
        count = count_row[0] if count_row else 0

        await self._db.execute("DELETE FROM events")
        await self._db.commit()
        logger.info("Cleared all %d events", count)
        return count

    async def get_event_count(self) -> int:
        """Get the total number of events."""
        cursor = await self._db.execute("SELECT COUNT(*) FROM events")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def close(self):
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Event store closed.")
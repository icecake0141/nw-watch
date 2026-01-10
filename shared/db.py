"""Database operations for network device monitoring."""

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager with simple retry support."""

    def __init__(self, db_path: str, history_size: int = 10, retry_attempts: int = 5):
        """Initialize database connection."""
        self.db_path = Path(db_path)
        self.history_size = history_size
        self.conn = self._connect_with_retry(retry_attempts)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _connect_with_retry(self, attempts: int) -> sqlite3.Connection:
        delay = 1
        for attempt in range(attempts):
            try:
                return sqlite3.connect(str(self.db_path), check_same_thread=False)
            except sqlite3.Error as exc:
                logger.error(
                    "SQLite connection error (attempt %s/%s) for %s: %s",
                    attempt + 1,
                    attempts,
                    self.db_path,
                    exc,
                )
                if attempt == attempts - 1:
                    raise
                time.sleep(min(5, delay))
                delay = min(5, delay * 2)

    def _init_schema(self):
        """Create database schema."""
        cursor = self.conn.cursor()

        # Devices table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """
        )

        # Commands table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_text TEXT UNIQUE NOT NULL
            )
        """
        )

        # Runs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                command_id INTEGER NOT NULL,
                ts_epoch INTEGER NOT NULL,
                output_text TEXT,
                ok INTEGER NOT NULL,
                error_message TEXT,
                duration_ms REAL,
                is_filtered INTEGER DEFAULT 0,
                is_truncated INTEGER DEFAULT 0,
                original_line_count INTEGER,
                FOREIGN KEY (device_id) REFERENCES devices(id),
                FOREIGN KEY (command_id) REFERENCES commands(id)
            )
        """
        )

        # Ping samples table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ping_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                ts_epoch INTEGER NOT NULL,
                ok INTEGER NOT NULL,
                rtt_ms REAL,
                error_message TEXT,
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        """
        )

        # Create indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_device_command ON runs(device_id, command_id)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_ts ON runs(ts_epoch)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ping_device_ts ON ping_samples(device_id, ts_epoch)"
        )

        self.conn.commit()

    def get_or_create_device(self, name: str) -> int:
        """Get or create device, return device ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM devices WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("INSERT INTO devices (name) VALUES (?)", (name,))
        self.conn.commit()
        return cursor.lastrowid

    def get_or_create_command(self, command_text: str) -> int:
        """Get or create command, return command ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM commands WHERE command_text = ?", (command_text,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute(
            "INSERT INTO commands (command_text) VALUES (?)", (command_text,)
        )
        self.conn.commit()
        return cursor.lastrowid

    def insert_run(
        self,
        device_name: str,
        command_text: str,
        ts_epoch: int,
        output_text: str,
        ok: bool,
        error_message: Optional[str] = None,
        duration_ms: Optional[float] = None,
        is_filtered: bool = False,
        is_truncated: bool = False,
        original_line_count: int = 0,
    ):
        """Insert a command run record."""
        device_id = self.get_or_create_device(device_name)
        command_id = self.get_or_create_command(command_text)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO runs (device_id, command_id, ts_epoch, output_text, ok,
                            error_message, duration_ms, is_filtered, is_truncated,
                            original_line_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                device_id,
                command_id,
                ts_epoch,
                output_text,
                1 if ok else 0,
                error_message,
                duration_ms,
                1 if is_filtered else 0,
                1 if is_truncated else 0,
                original_line_count,
            ),
        )
        self.conn.commit()

        # Clean up old runs, keep only configured history_size
        self._cleanup_old_runs(device_id, command_id)

    def _cleanup_old_runs(self, device_id: int, command_id: int):
        """Remove old runs, keeping only the most recent history_size."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            DELETE FROM runs
            WHERE device_id = ? AND command_id = ?
            AND id NOT IN (
                SELECT id FROM runs
                WHERE device_id = ? AND command_id = ?
                ORDER BY ts_epoch DESC
                LIMIT ?
            )
        """,
            (
                device_id,
                command_id,
                device_id,
                command_id,
                self.history_size,
            ),
        )
        self.conn.commit()

    def insert_ping_sample(
        self,
        device_name: str,
        ts_epoch: int,
        ok: bool,
        rtt_ms: Optional[float] = None,
        error_message: Optional[str] = None,
    ):
        """Insert a ping sample."""
        device_id = self.get_or_create_device(device_name)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO ping_samples (device_id, ts_epoch, ok, rtt_ms, error_message)
            VALUES (?, ?, ?, ?, ?)
        """,
            (device_id, ts_epoch, 1 if ok else 0, rtt_ms, error_message),
        )
        self.conn.commit()

    def get_latest_runs(
        self,
        device_name: str,
        command_text: str,
        limit: int = 10,
        include_filtered: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get latest runs for a device/command combination."""
        cursor = self.conn.cursor()
        sql = """
            SELECT r.* FROM runs r
            JOIN devices d ON r.device_id = d.id
            JOIN commands c ON r.command_id = c.id
            WHERE d.name = ? AND c.command_text = ?
        """
        params: List[Any] = [device_name, command_text]
        if not include_filtered:
            sql += " AND r.is_filtered = 0"
        sql += " ORDER BY r.ts_epoch DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_latest_run(
        self, device_name: str, command_text: str, include_filtered: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent run for a device/command."""
        runs = self.get_latest_runs(
            device_name, command_text, limit=1, include_filtered=include_filtered
        )
        return runs[0] if runs else None

    def get_all_commands(self) -> List[str]:
        """Get all unique commands."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT command_text FROM commands ORDER BY command_text")
        return [row[0] for row in cursor.fetchall()]

    def get_all_devices(self) -> List[str]:
        """Get all unique devices."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM devices ORDER BY name")
        return [row[0] for row in cursor.fetchall()]

    def get_ping_samples(self, device_name: str, since_ts: int) -> List[Dict[str, Any]]:
        """Get ping samples for a device since a given timestamp."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT p.* FROM ping_samples p
            JOIN devices d ON p.device_id = d.id
            WHERE d.name = ? AND p.ts_epoch >= ?
            ORDER BY p.ts_epoch DESC
        """,
            (device_name, since_ts),
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def close(self):
        """Close database connection."""
        self.conn.close()

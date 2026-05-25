"""Configuration file watcher for hot reload."""

import asyncio
import logging
import hashlib
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """Monitors configuration file for changes and triggers callbacks."""

    def __init__(self, config_path: Path = Path("config.yaml")):
        self._config_path = config_path
        self._last_hash: Optional[str] = None
        self._callback: Optional[Callable] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._check_interval = 5  # seconds

    async def start(self, callback: Callable):
        """Start watching the config file for changes.

        Args:
            callback: Async callable invoked when config file changes.
        """
        self._callback = callback
        self._running = True

        # Get initial hash
        if self._config_path.exists():
            self._last_hash = self._get_file_hash(self._config_path)
            logger.info("Config watcher started for: %s", self._config_path)
        else:
            logger.warning("Config file not found: %s", self._config_path)

        self._task = asyncio.create_task(self._watch_loop())

    async def stop(self):
        """Stop watching the config file."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Config watcher stopped.")

    async def _watch_loop(self):
        """Main watch loop."""
        while self._running:
            try:
                await asyncio.sleep(self._check_interval)
                await self._check_for_changes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in config watcher: %s", e)

    async def _check_for_changes(self):
        """Check if the config file has changed."""
        if not self._config_path.exists():
            if self._last_hash is not None:
                logger.warning("Config file disappeared: %s", self._config_path)
            return

        current_hash = self._get_file_hash(self._config_path)

        if current_hash != self._last_hash:
            logger.info("Configuration file changed, reloading...")
            self._last_hash = current_hash
            if self._callback:
                try:
                    await self._callback()
                except Exception as e:
                    logger.error("Error in config reload callback: %s", e)

    @staticmethod
    def _get_file_hash(file_path: Path) -> str:
        """Get MD5 hash of a file."""
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
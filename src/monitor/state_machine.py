"""Electricity status state machine."""

import logging
from enum import Enum
from datetime import datetime
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ElectricityStatus(Enum):
    """Electricity status values."""
    ON = "ON"
    OFF = "OFF"
    UNKNOWN = "N/A"


@dataclass
class StatusEvent:
    """A recorded electricity status change event."""
    timestamp: datetime
    status: ElectricityStatus
    previous_status: Optional[ElectricityStatus] = None


class StateMachine:
    """Monitors consecutive check results and determines electricity status.

    Implements the decision rules:
    - OFF after 2 consecutive failed checks
    - ON after 2 consecutive successful checks
    - UNKNOWN until enough checks have been made
    """

    SUCCESS_THRESHOLD = 2
    FAILURE_THRESHOLD = 2

    def __init__(self, last_state_file: str = "./data/last_state.json"):
        self._consecutive_successes = 0
        self._consecutive_failures = 0
        self._current_status = ElectricityStatus.UNKNOWN
        self._last_event: Optional[StatusEvent] = None
        self._last_state_file = last_state_file
        self._on_status_change: Optional[Callable] = None
        self._initialized = False

    @property
    def current_status(self) -> ElectricityStatus:
        return self._current_status

    @property
    def last_event(self) -> Optional[StatusEvent]:
        return self._last_event

    @property
    def last_check_time(self) -> Optional[datetime]:
        """Get the timestamp of the last status event."""
        if self._last_event:
            return self._last_event.timestamp
        return None

    def set_callback(self, callback: Callable[[ElectricityStatus, ElectricityStatus], Awaitable[None]]):
        """Set callback for status change notifications."""
        self._on_status_change = callback

    def initialize_from_file(self):
        """Restore state from the last_state_file if it exists."""
        path = Path(self._last_state_file)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                saved_status = data.get("status")
                saved_timestamp = data.get("timestamp")

                if saved_status in ("ON", "OFF"):
                    self._current_status = ElectricityStatus(saved_status)
                    self._consecutive_successes = self.SUCCESS_THRESHOLD if saved_status == "ON" else 0
                    self._consecutive_failures = self.SUCCESS_THRESHOLD if saved_status == "OFF" else 0

                    if saved_timestamp:
                        self._last_event = StatusEvent(
                            timestamp=datetime.fromisoformat(saved_timestamp),
                            status=self._current_status
                        )
                    logger.info("State restored from %s: status=%s", path, saved_status)
                else:
                    logger.warning("Invalid saved status in %s: %s", path, saved_status)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error("Failed to load state from %s: %s", path, e)
        else:
            logger.info("No last state file found at %s, starting fresh", path)

        self._initialized = True

    def save_state(self):
        """Save current state to the last_state_file."""
        path = Path(self._last_state_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "status": self._current_status.value,
            "timestamp": self._last_event.timestamp.isoformat() if self._last_event else datetime.now().isoformat()
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug("State saved to %s", path)
        except OSError as e:
            logger.error("Failed to save state to %s: %s", path, e)

    async def process_check_result(self, success: bool) -> Optional[ElectricityStatus]:
        """Process a TCP check result and update status if needed.

        Args:
            success: Whether the TCP check was successful.

        Returns:
            New status if it changed, None otherwise.
        """
        if not self._initialized:
            self.initialize_from_file()
            self._initialized = True

        previous_status = self._current_status

        if success:
            self._consecutive_successes += 1
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
            self._consecutive_successes = 0

        # Check for status transitions
        new_status = None

        if self._consecutive_failures >= self.FAILURE_THRESHOLD:
            new_status = ElectricityStatus.OFF
        elif self._consecutive_successes >= self.SUCCESS_THRESHOLD:
            new_status = ElectricityStatus.ON

        if new_status and new_status != self._current_status:
            self._current_status = new_status
            self._last_event = StatusEvent(
                timestamp=datetime.now(),
                status=new_status,
                previous_status=previous_status
            )
            self.save_state()

            logger.info(
                "Status changed: %s -> %s (consecutive: %d/%d)",
                previous_status.value if previous_status else "N/A",
                new_status.value,
                self._consecutive_successes,
                self._consecutive_failures
            )

            # Notify callback if status changed to/from OFF
            if new_status == ElectricityStatus.OFF or previous_status == ElectricityStatus.OFF:
                return new_status

        return None

    def reset(self):
        """Reset the state machine to initial state."""
        self._consecutive_successes = 0
        self._consecutive_failures = 0
        self._current_status = ElectricityStatus.UNKNOWN
        self._last_event = None
        self._initialized = False

    def force_status(self, status: ElectricityStatus):
        """Force set the status (for manual refresh)."""
        previous_status = self._current_status
        if status != self._current_status:
            self._current_status = status
            self._last_event = StatusEvent(
                timestamp=datetime.now(),
                status=status,
                previous_status=previous_status
            )
            self.save_state()
            logger.info("Status forced: %s -> %s", previous_status.value if previous_status else "N/A", status.value)
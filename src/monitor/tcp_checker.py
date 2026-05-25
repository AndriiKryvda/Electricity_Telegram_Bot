"""TCP connection checker for device monitoring."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a TCP connection check."""
    success: bool
    host: str
    port: int
    timestamp: datetime
    duration_ms: float
    error: Optional[str] = None


class TCPChecker:
    """Performs TCP connection checks to a monitored device."""

    def __init__(self, host: str, port: int, timeout: int = 15):
        """Initialize the TCP checker.

        Args:
            host: Device hostname or IP address.
            port: Device TCP port.
            timeout: Connection timeout in seconds (default 15).
        """
        self._host = host
        self._port = port
        self._timeout = timeout

    @property
    def host(self) -> str:
        return self._host

    @host.setter
    def host(self, value: str):
        self._host = value

    @property
    def port(self) -> int:
        return self._port

    @port.setter
    def port(self, value: int):
        self._port = value

    async def check(self) -> CheckResult:
        """Perform a TCP connection check.

        Returns:
            CheckResult with the result of the connection attempt.
        """
        start_time = asyncio.get_event_loop().time()

        try:
            reader, _ = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=self._timeout
            )
            # Connection successful, close immediately
            reader.close()
            await reader.wait_closed()
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            logger.debug(
                "TCP check successful to %s:%d (%.0fms)",
                self._host, self._port, duration_ms
            )
            return CheckResult(
                success=True,
                host=self._host,
                port=self._port,
                timestamp=datetime.now(),
                duration_ms=duration_ms
            )

        except asyncio.TimeoutError:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            error_msg = f"Connection timed out after {self._timeout}s"
            logger.debug(
                "TCP check failed to %s:%d - %s (%.0fms)",
                self._host, self._port, error_msg, duration_ms
            )
            return CheckResult(
                success=False,
                host=self._host,
                port=self._port,
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                error=error_msg
            )

        except (OSError, ConnectionError) as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            error_msg = str(e) or f"Connection refused to {self._host}:{self._port}"
            logger.debug(
                "TCP check failed to %s:%d - %s (%.0fms)",
                self._host, self._port, error_msg, duration_ms
            )
            return CheckResult(
                success=False,
                host=self._host,
                port=self._port,
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                error=error_msg
            )

        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(
                "Unexpected TCP check error for %s:%d - %s",
                self._host, self._port, error_msg
            )
            return CheckResult(
                success=False,
                host=self._host,
                port=self._port,
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                error=error_msg
            )

    def update_config(self, host: str, port: int):
        """Update the host and port for the checker."""
        self._host = host
        self._port = port
        logger.info("TCP checker updated: %s:%d", host, port)
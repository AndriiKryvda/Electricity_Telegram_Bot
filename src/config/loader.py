"""Configuration loader with validation."""

import os
import re
import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_CONFIG = {
    "bot": {
        "token": "",
        "admin_user_ids": [],
    },
    "device": {
        "host": "127.0.0.1",
        "port": 8080,
        "poll_interval": 60,
    },
    "server": {
        "last_state_file": "./data/last_state.json",
    },
}

CONFIG_PATH = Path("config.yaml")


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class Config:
    """Bot configuration holder."""

    def __init__(self, data: dict):
        self._data = data
        self._device_config = data.get("device", {})
        self._bot_config = data.get("bot", {})
        self._server_config = data.get("server", {})

    @property
    def bot_token(self) -> str:
        return self._bot_config.get("token", "")

    @property
    def admin_user_ids(self) -> list[int]:
        return self._bot_config.get("admin_user_ids", [])

    @property
    def device_host(self) -> str:
        return self._device_config.get("host", "127.0.0.1")

    @device_host.setter
    def device_host(self, value: str):
        self._device_config["host"] = value

    @property
    def device_port(self) -> int:
        return self._device_config.get("port", 8080)

    @device_port.setter
    def device_port(self, value: int):
        self._device_config["port"] = value

    @property
    def poll_interval(self) -> int:
        return self._device_config.get("poll_interval", 60)

    @poll_interval.setter
    def poll_interval(self, value: int):
        self._device_config["poll_interval"] = value

    @property
    def last_state_file(self) -> str:
        return self._server_config.get("last_state_file", "./data/last_state.json")

    @property
    def db_path(self) -> str:
        """Get the database file path."""
        # Derive from last_state_file path's directory
        state_dir = Path(self.last_state_file).parent
        return str(Path(state_dir) / "electricity.db")

    def to_dict(self) -> dict:
        """Return the full configuration as a dictionary."""
        return self._data

    def has_valid_token(self) -> bool:
        """Check if the bot token is valid."""
        token = self.bot_token.strip()
        return len(token) > 10 and ":" in token

    def is_admin(self, user_id: int) -> bool:
        """Check if a user is authorized to use the bot."""
        return user_id in self.admin_user_ids


def _validate_ipv4(host: str) -> bool:
    """Validate an IPv4 address."""
    pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
    match = re.match(pattern, host)
    if not match:
        return False
    for octet in match.groups():
        if int(octet) > 255:
            return False
    return True


def _validate_hostname(host: str) -> bool:
    """Validate a hostname."""
    if len(host) > 253:
        return False
    pattern = r"^(?=.{1,253}$)([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z]{2,}$"
    return bool(re.match(pattern, host))


def _validate_host(host: str) -> bool:
    """Validate IP or hostname."""
    if not host or not host.strip():
        return False
    return _validate_ipv4(host.strip()) or _validate_hostname(host.strip())


def _validate_port(port: int) -> bool:
    """Validate port number."""
    return isinstance(port, int) and 1 <= port <= 65535


def _validate_poll_interval(interval: int) -> bool:
    """Validate poll interval."""
    return isinstance(interval, int) and 30 <= interval <= 120


def _validate_admin_ids(ids: list) -> list[int]:
    """Validate and convert admin user IDs."""
    valid_ids: list[int] = []
    for uid in ids:
        if isinstance(uid, int) and uid > 0:
            valid_ids.append(uid)
        elif isinstance(uid, str):
            try:
                val = int(uid)
                if val > 0:
                    valid_ids.append(val)
            except ValueError:
                logger.warning(f"Skipping invalid admin user ID: {uid!r}")
    return valid_ids


def _load_config_from_yaml(path: Path) -> dict:
    """Load configuration from a YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _apply_defaults(data: dict) -> dict:
    """Apply default values for missing keys."""
    # Bot section
    if "bot" not in data:
        data["bot"] = {}
    if "token" not in data["bot"]:
        data["bot"]["token"] = ""
    if "admin_user_ids" not in data["bot"]:
        data["bot"]["admin_user_ids"] = []

    # Device section
    if "device" not in data:
        data["device"] = {}
    if "host" not in data["device"]:
        data["device"]["host"] = DEFAULT_CONFIG["device"]["host"]
    if "port" not in data["device"]:
        data["device"]["port"] = DEFAULT_CONFIG["device"]["port"]
    if "poll_interval" not in data["device"]:
        data["device"]["poll_interval"] = DEFAULT_CONFIG["device"]["poll_interval"]

    # Server section
    if "server" not in data:
        data["server"] = {}
    if "last_state_file" not in data["server"]:
        data["server"]["last_state_file"] = DEFAULT_CONFIG["server"]["last_state_file"]

    return data


def load_config(path: Optional[Path] = None) -> Config:
    """Load and validate configuration.

    Args:
        path: Path to the config file. Defaults to CONFIG_PATH.

    Returns:
        Config: Validated configuration object.

    Raises:
        ConfigValidationError: If required configuration is invalid.
        FileNotFoundError: If config file does not exist.
    """
    config_path = path or CONFIG_PATH

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    try:
        raw_data = _load_config_from_yaml(config_path)
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"Failed to parse config.yaml: {e}")

    # Apply defaults
    raw_data = _apply_defaults(raw_data)

    # Validate bot token
    token = raw_data.get("bot", {}).get("token", "")
    if not token or not str(token).strip():
        raise ConfigValidationError(
            "Bot token is empty or missing. Set 'bot.token' in config.yaml."
        )

    # Validate host
    host = str(raw_data.get("device", {}).get("host", ""))
    if not _validate_host(host):
        raise ConfigValidationError(
            f"Invalid device host: {host!r}. Must be a valid IPv4 address or hostname."
        )

    # Validate port
    port = raw_data.get("device", {}).get("port", 0)
    if not _validate_port(port):
        raise ConfigValidationError(
            f"Invalid device port: {port}. Must be between 1 and 65535."
        )

    # Validate poll interval
    poll_interval = raw_data.get("device", {}).get("poll_interval", 0)
    if not _validate_poll_interval(poll_interval):
        raise ConfigValidationError(
            f"Invalid poll interval: {poll_interval}. Must be between 30 and 120 seconds."
        )

    # Validate admin user IDs
    admin_ids = _validate_admin_ids(raw_data.get("bot", {}).get("admin_user_ids", []))
    if not admin_ids:
        logger.warning("No admin user IDs configured. All authenticated users will be denied.")

    raw_data["bot"]["admin_user_ids"] = admin_ids

    config = Config(raw_data)
    logger.info("Configuration loaded successfully from %s", config_path)
    return config


def reload_config(path: Optional[Path] = None) -> Config:
    """Reload configuration from file.

    Args:
        path: Path to the config file. Defaults to CONFIG_PATH.

    Returns:
        Config: Reloaded configuration object.
    """
    return load_config(path)


def validate_device_config(host: str, port: int, poll_interval: int) -> tuple[bool, str]:
    """Validate device configuration values.

    Args:
        host: Device hostname or IP.
        port: Device port.
        poll_interval: Poll interval in seconds.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not _validate_host(host):
        return False, f"Invalid device host: {host!r}"
    if not _validate_port(port):
        return False, f"Invalid device port: {port}. Must be 1-65535."
    if not _validate_poll_interval(poll_interval):
        return False, f"Invalid poll interval: {poll_interval}. Must be 30-120."
    return True, ""
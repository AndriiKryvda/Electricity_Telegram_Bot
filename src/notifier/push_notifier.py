"""Push notification system for electricity status changes."""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Set, Dict
from aiogram import Bot

logger = logging.getLogger(__name__)


class PushNotifier:
    """Sends push notifications to authorized Telegram users on status changes."""

    def __init__(self, bot: Bot, admin_user_ids: list[int], dedup_window: int = 30):
        """Initialize the push notifier.

        Args:
            bot: The aiogram Bot instance.
            admin_user_ids: List of authorized Telegram user IDs.
            dedup_window: Seconds to suppress notifications after a user checks status (default 30).
        """
        self._bot = bot
        self._admin_user_ids = set(admin_user_ids)
        self._dedup_window = dedup_window
        # Track last notification time per user
        self._last_notification: Dict[int, datetime] = {}

    @property
    def admin_user_ids(self) -> Set[int]:
        return set(self._admin_user_ids)

    def update_admin_ids(self, admin_ids: list[int]):
        """Update the admin user IDs list."""
        self._admin_user_ids = set(admin_ids)

    def user_checked_recently(self, user_id: int) -> bool:
        """Check if a user checked status within the dedup window."""
        last_check = self._last_notification.get(user_id)
        if last_check:
            return (datetime.now() - last_check).total_seconds() < self._dedup_window
        return False

    def record_user_check(self, user_id: int):
        """Record that a user just checked their status."""
        self._last_notification[user_id] = datetime.now()

    async def notify_status_change(self, status: str, user_id: Optional[int] = None):
        """Notify about a status change.

        Args:
            status: "ON" or "OFF".
            user_id: If provided, skip dedup for this user (they triggered the check).
        """
        # Emoji indicator
        emoji = "\U0001F4A1"  # Sparkle
        status_text = "Electricity: " + status
        timestamp = datetime.now().strftime("%H:%M")

        message = f"{emoji} {status_text} at {timestamp}."

        if user_id:
            # Notify only the specific user
            try:
                await self._bot.send_message(user_id, message)
                logger.info("Sent status notification to user %d: %s", user_id, message)
            except Exception as e:
                logger.error("Failed to send notification to user %d: %s", user_id, e)
        else:
            # Broadcast to all admin users with dedup
            for admin_id in self._admin_user_ids:
                if not self.user_checked_recently(admin_id):
                    try:
                        await self._bot.send_message(admin_id, message)
                        logger.info("Sent status notification to admin %d: %s", admin_id, message)
                    except Exception as e:
                        logger.error("Failed to send notification to admin %d: %s", admin_id, e)
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.5)

    async def notify_all_users(self, message: str):
        """Send a general message to all admin users."""
        for admin_id in self._admin_user_ids:
            try:
                await self._bot.send_message(admin_id, message)
                logger.info("Sent general message to admin %d", admin_id)
            except Exception as e:
                logger.error("Failed to send message to admin %d: %s", admin_id, e)
            await asyncio.sleep(0.5)

    def cleanup_old_entries(self):
        """Remove old dedup entries to prevent memory leaks."""
        cutoff = datetime.now() - timedelta(seconds=self._dedup_window * 2)
        old_keys = [k for k, v in self._last_notification.items() if v < cutoff]
        for key in old_keys:
            del self._last_notification[key]
        if old_keys:
            logger.debug("Cleaned up %d old dedup entries", len(old_keys))
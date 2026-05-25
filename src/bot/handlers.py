"""Command and callback handlers for the Telegram bot."""

import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from ..config.loader import Config, reload_config
from ..monitor.state_machine import ElectricityStatus
from ..monitor.tcp_checker import TCPChecker
from ..storage.events import EventStore
from ..notifier.push_notifier import PushNotifier
from .keyboards import refresh_keyboard, stats_keyboard, confirm_clear_keyboard

logger = logging.getLogger(__name__)

# Format duration string for display
def format_duration(td: Optional[datetime], ref: Optional[datetime]) -> Optional[str]:
    """Format duration between two datetimes as human-readable string."""
    if not td or not ref:
        return None
    diff = ref - td
    total_seconds = int(diff.total_seconds())
    if total_seconds < 0:
        return None

    days = total_seconds // 86400
    remaining = total_seconds % 86400
    hours = remaining // 3600
    minutes = (remaining % 3600) // 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if days == 0 and hours == 0:
        parts.append(f"{minutes}m")
    elif minutes > 0:
        parts.append(f"{minutes}m")

    return " ".join(parts) if parts else "0m"


def format_status_emoji(status: ElectricityStatus) -> str:
    """Get emoji for electricity status."""
    mapping = {
        ElectricityStatus.ON: "\U0001F4A1",
        ElectricityStatus.OFF: "\u26AB",
        ElectricityStatus.UNKNOWN: "\u26AA",
    }
    return mapping.get(status, "\u26AA")


def format_status_text(status: ElectricityStatus) -> str:
    """Get display text for electricity status."""
    mapping = {
        ElectricityStatus.ON: "Electricity: ON",
        ElectricityStatus.OFF: "Electricity: OFF",
        ElectricityStatus.UNKNOWN: "Electricity: Unknown",
    }
    return mapping.get(status, "Electricity: Unknown")


def format_last_check(last_check_time: Optional[datetime]) -> str:
    """Format last check time for display."""
    if last_check_time:
        return f"Last check: {last_check_time.strftime('%d-%b-%Y %H:%M')}"
    return "Last check: N/A"


async def _send_with_retry(bot: Bot, chat_id: int, text: str, **kwargs):
    """Send a message with retry handling."""
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logger.error("Failed to send message to %d: %s", chat_id, e)


async def _edit_with_retry(bot: Bot, chat_id: int, message_id: int, text: str, **kwargs):
    """Edit a message, silently ignoring 'message not modified' errors."""
    try:
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, **kwargs)
    except Exception as e:
        error_str = str(e).lower()
        if "message is not modified" in error_str or "can't update the message" in error_str:
            logger.debug("Message not modified, skipping edit for msg %d", message_id)
        else:
            logger.error("Failed to edit message %d: %s", message_id, e)


# Status command handler
async def cmd_status(message: Message, bot: Bot, config: Config = None, state_machine = None, event_store: EventStore = None):
    """Handle /status command."""
    if state_machine is None:
        await _send_with_retry(bot, message.chat.id, "⚠️ Service unavailable. Please try again later.")
        return
    status = state_machine.current_status
    emoji = format_status_emoji(status)
    text = f"{emoji} {format_status_text(status)}\n\n{format_last_check(state_machine.last_check_time)}"

    await _send_with_retry(
        bot, message.chat.id, text,
        parse_mode="HTML",
        reply_markup=refresh_keyboard()
    )


# Stats command handler
async def cmd_stats(message: Message, bot: Bot, config: Config = None, state_machine = None, event_store: EventStore = None):
    """Handle /stats command."""
    if state_machine is None or event_store is None:
        await _send_with_retry(bot, message.chat.id, "⚠️ Service unavailable. Please try again later.")
        return
    # Purge old events first
    await event_store.purge_old_events(3)

    # Get current status
    status = state_machine.current_status
    emoji = format_status_emoji(status)
    header = f"{emoji} {format_status_text(status)}\n\n"

    # Get events
    events = await event_store.get_events(50)

    if not events:
        text = header + "\u2139\uFE0F No events recorded yet."
        await _send_with_retry(
            bot, message.chat.id, text,
            parse_mode="HTML",
            reply_markup=stats_keyboard()
        )
        return

    # Build history table
    lines = [header, "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500", "\u2B50 History:"]

    ref_time = None
    for i, event in enumerate(events):
        if i == 0:
            ref_time = datetime.now()

        # Format timestamp
        ts = event.timestamp.strftime('%d-%b-%Y %H:%M')

        # Format status with color
        if event.status == "ON":
            status_display = f"<code>{event.status}</code>"
        else:
            status_display = f"<code>{event.status}</code>"

        # Format duration
        duration = "N/A"
        if event.duration:
            duration = event.duration
        elif event.previous_status:
            duration = "N/A"

        lines.append(f"<code>{ts}</code>  {status_display}  ({duration})")

        ref_time = event.timestamp

    lines.append("\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

    text = "\n".join(lines)

    await _send_with_retry(
        bot, message.chat.id, text,
        parse_mode="HTML",
        reply_markup=stats_keyboard()
    )


# Reload command handler
async def cmd_reload(message: Message, bot: Bot, config: Config):
    """Handle /reload command."""
    try:
        new_config = reload_config()
        return "Configuration reloaded."
    except Exception as e:
        logger.error("Config reload failed: %s", e)
        return f"Config reload failed: {str(e)}"


# Help command handler
async def cmd_help(message: Message, bot: Bot):
    """Handle /help command."""
    text = (
        "\u26A1 <b>Electricity Status Bot</b>\n\n"
        "<b>Available commands:</b>\n"
        "/status - Show current electricity status\n"
        "/stats - Show electricity status and outage history\n"
        "/reload - Reload configuration file\n"
        "/help - Show this help message"
    )
    await _send_with_retry(bot, message.chat.id, text, parse_mode="HTML")


# Callback query handler
async def handle_callback(callback: CallbackQuery, bot: Bot, config: Config = None,
                          state_machine = None, event_store: EventStore = None, notifier: PushNotifier = None):
    """Handle inline keyboard callback queries."""
    if state_machine is None or event_store is None or notifier is None:
        await _edit_with_retry(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            "⚠️ Service unavailable. Please try again later.",
        )
        await callback.answer()
        return

    data = callback.data
    user_id = callback.from_user.id

    if data == "refresh":
        # Trigger immediate TCP check
        checker = TCPChecker(config.device_host, config.device_port)
        result = await checker.check()
        new_status = await state_machine.process_check_result(result.success)

        status = state_machine.current_status
        emoji = format_status_emoji(status)
        text = f"{emoji} {format_status_text(status)}\n\n{format_last_check(state_machine.last_check_time)}"

        await _edit_with_retry(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            text,
            parse_mode="HTML",
            reply_markup=refresh_keyboard()
        )

        # Record user check for dedup
        notifier.record_user_check(user_id)

        # Notify on state change
        if new_status:
            await notifier.notify_status_change(new_status.value, user_id)

    elif data == "refresh_stats":
        # Purge old events
        await event_store.purge_old_events(3)

        status = state_machine.current_status
        emoji = format_status_emoji(status)
        header = f"{emoji} {format_status_text(status)}\n\n"

        events = await event_store.get_events(50)

        if not events:
            text = header + "\u2139\uFE0F No events recorded yet."
            await _edit_with_retry(
                bot,
                callback.message.chat.id,
                callback.message.message_id,
                text,
                parse_mode="HTML",
                reply_markup=stats_keyboard()
            )
            return

        lines = [header, "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500", "\u2B50 History:"]
        ref_time = None
        for i, event in enumerate(events):
            if i == 0:
                ref_time = datetime.now()

            ts = event.timestamp.strftime('%d-%b-%Y %H:%M')
            status_display = f"<code>{event.status}</code>"
            duration = event.duration if event.duration else "N/A"

            lines.append(f"<code>{ts}</code>  {status_display}  ({duration})")
            ref_time = event.timestamp

        lines.append("\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
        text = "\n".join(lines)

        await _edit_with_retry(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            text,
            parse_mode="HTML",
            reply_markup=stats_keyboard()
        )

    elif data == "clear_events":
        await _edit_with_retry(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            "\u26A0\uFE0F Are you sure you want to clear all events?",
            reply_markup=confirm_clear_keyboard()
        )

    elif data == "confirm_clear_yes":
        await event_store.clear_all_events()
        status = state_machine.current_status
        emoji = format_status_emoji(status)
        text = f"{emoji} {format_status_text(status)}\n\n\u2705 All events cleared."

        await _edit_with_retry(
            bot,
            callback.message.chat.id,
            callback.message.message_id,
            text,
            parse_mode="HTML",
            reply_markup=stats_keyboard()
        )

    elif data == "confirm_clear_no":
        # Revert to stats view
        await callback.answer("Cleared.")
        # Don't change the keyboard, keep the confirm view

    # Acknowledge the callback
    await callback.answer()
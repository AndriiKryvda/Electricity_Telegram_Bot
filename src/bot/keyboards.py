"""Inline keyboard definitions for the Telegram bot."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def refresh_keyboard() -> InlineKeyboardMarkup:
    """Create a refresh inline keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="\U0001F504 Refresh", callback_data="refresh")]
    ])
    return keyboard


def stats_keyboard() -> InlineKeyboardMarkup:
    """Create stats inline keyboard with refresh and clear buttons."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\U0001F504 Refresh", callback_data="refresh_stats"),
            InlineKeyboardButton(text="\U0001F5D1\uFE0F Clear", callback_data="clear_events")
        ]
    ])
    return keyboard


def confirm_clear_keyboard() -> InlineKeyboardMarkup:
    """Create confirmation keyboard for clearing events."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\u2705 Yes, Clear", callback_data="confirm_clear_yes"),
            InlineKeyboardButton(text="\u274C Cancel", callback_data="confirm_clear_no")
        ]
    ])
    return keyboard
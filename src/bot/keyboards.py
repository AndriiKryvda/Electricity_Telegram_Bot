"""Keyboard definitions for the Telegram bot."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


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


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Create the main reply keyboard menu with command buttons."""
    from aiogram.types import KeyboardButton
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [
                KeyboardButton(text="\u26A1 Status", command="status"),
                KeyboardButton(text="\U0001F4CA Stats", command="stats"),
            ],
            [
                KeyboardButton(text="\U0001F527 Reload", command="reload"),
                KeyboardButton(text="\u2753 Help", command="help"),
            ],
        ]
    )


def command_menu_keyboard() -> InlineKeyboardMarkup:
    """Create an inline command menu keyboard."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\u26A1 Status", callback_data="menu_status"),
            InlineKeyboardButton(text="\U0001F4CA Stats", callback_data="menu_stats"),
        ],
        [
            InlineKeyboardButton(text="\U0001F527 Reload", callback_data="menu_reload"),
            InlineKeyboardButton(text="\u2753 Help", callback_data="menu_help"),
        ],
    ])
    return keyboard

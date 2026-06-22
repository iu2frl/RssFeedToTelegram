"""Telegram bot instance holder and initialization."""

import telebot

from . import config

# Shared Telegram bot instance (initialized at startup via init_bot)
telegram_bot: telebot.TeleBot = None


# Bot initialization
def init_bot() -> telebot.TeleBot:
    """Initialize the Telegram bot class"""
    global telegram_bot
    telegram_bot = telebot.TeleBot(config.get_bot_api_from_env())
    return telegram_bot

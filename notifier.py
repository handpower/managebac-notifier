"""Telegram notification sender via Bot API"""

import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class NotificationError(Exception):
    pass


class TelegramNotifier:
    """Sync Telegram Bot API client"""

    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.client = httpx.Client(timeout=30.0)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _api_url(self, method):
        return f"{TELEGRAM_API_BASE}{self.bot_token}/{method}"

    def _call(self, method, payload):
        """Call Telegram Bot API with retry"""
        url = self._api_url(method)
        last_error = None
        for attempt in range(3):
            try:
                resp = self.client.post(url, json=payload)
                result = resp.json()
                if not resp.is_success:
                    logger.error(f"HTTP {resp.status_code}: {result}")
                    last_error = result
                    continue
                if result.get("ok"):
                    return result.get("result")
                else:
                    logger.error(f"Telegram API error: {result}")
                    last_error = result
            except httpx.HTTPError as e:
                logger.warning(f"Attempt {attempt + 1}/3 failed: {e}")
                last_error = e
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise NotificationError(f"Failed after 3 attempts: {last_error}")

    def send_message(self, text, parse_mode="HTML", reply_markup=None):
        """Send a message, optionally with inline keyboard"""
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = self._call("sendMessage", payload)
        logger.info("Telegram message sent successfully")
        return result

    def edit_message_text(self, message_id, text, parse_mode="HTML", reply_markup=None):
        """Edit an existing message"""
        payload = {
            "chat_id": self.chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._call("editMessageText", payload)

    def answer_callback_query(self, callback_query_id, text=""):
        """Answer a callback query (dismiss loading indicator)"""
        return self._call("answerCallbackQuery", {
            "callback_query_id": callback_query_id,
            "text": text,
        })

    def get_updates(self, offset=None, timeout=0):
        """Get pending updates from the bot (long polling, no retry)"""
        payload = {"timeout": timeout, "allowed_updates": ["callback_query"]}
        if offset:
            payload["offset"] = offset
        url = self._api_url("getUpdates")
        resp = self.client.post(
            url, json=payload, timeout=timeout + 10
        )
        result = resp.json()
        if result.get("ok"):
            return result.get("result", [])
        raise NotificationError(f"getUpdates failed: {result}")

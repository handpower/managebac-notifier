"""Telegram notification sender via Bot API"""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

# Telegram hard limit is 4096 chars per message; leave headroom for safety.
MAX_MESSAGE_LENGTH = 4000


class NotificationError(Exception):
    pass


def _split_message(text, limit=MAX_MESSAGE_LENGTH):
    """Split text into chunks under `limit`, breaking on line boundaries.

    Lines are kept intact (so HTML tags like <a>...</a> never get cut in half).
    A single line longer than `limit` is hard-split as a last resort.
    """
    if len(text) <= limit:
        return [text]

    chunks = []
    current = []
    current_len = 0
    for line in text.split("\n"):
        # +1 accounts for the "\n" that rejoins this line to the previous one.
        line_cost = len(line) + (1 if current else 0)
        if current and current_len + line_cost > limit:
            chunks.append("\n".join(current))
            current, current_len = [], 0
            line_cost = len(line)

        while len(line) > limit:
            head, line = line[:limit], line[limit:]
            chunks.append(head)
        current.append(line)
        current_len += len(line) + (1 if len(current) > 1 else 0)

    if current:
        chunks.append("\n".join(current))
    return chunks


class TelegramNotifier:
    """Sync Telegram Bot API client"""

    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.client = httpx.Client(timeout=httpx.Timeout(30.0, connect=15.0))

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _api_url(self, method):
        return f"{TELEGRAM_API_BASE}{self.bot_token}/{method}"

    def _call(self, method, payload):
        """Call Telegram Bot API with retry and backoff"""
        url = self._api_url(method)
        last_error = None
        for attempt in range(4):
            try:
                resp = self.client.post(url, json=payload)
                result = resp.json()
                if not resp.is_success:
                    logger.warning(f"Attempt {attempt + 1}/4: HTTP {resp.status_code}: {result}")
                    last_error = result
                elif result.get("ok"):
                    return result.get("result")
                else:
                    logger.warning(f"Attempt {attempt + 1}/4: Telegram API error: {result}")
                    last_error = result
            except httpx.HTTPError as e:
                logger.warning(f"Attempt {attempt + 1}/4 failed: {e}")
                last_error = e
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
        raise NotificationError(f"Failed after 4 attempts: {last_error}")

    def send_message(self, text, parse_mode="HTML", reply_markup=None):
        """Send a message, splitting into multiple parts if over the length limit.

        The inline keyboard, if any, is attached only to the final part.
        Returns the result of the last send.
        """
        chunks = _split_message(text)
        result = None
        for i, chunk in enumerate(chunks):
            is_last = i == len(chunks) - 1
            payload = {
                "chat_id": self.chat_id,
                "text": chunk,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }
            if reply_markup and is_last:
                payload["reply_markup"] = reply_markup
            result = self._call("sendMessage", payload)
        logger.info(f"Telegram message sent successfully ({len(chunks)} part(s))")
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

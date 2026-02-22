#!/usr/bin/env python
"""Lightweight Telegram bot listener for handling ignore callbacks.

Runs as a persistent daemon via launchd. Polls getUpdates and processes:
- "manage" → sends interactive ignore-list message
- "ign:{task_id}" → toggles task ignore status, refreshes buttons
- "done" → deletes the manage message
- "noop" → does nothing (section header buttons)
"""

import json
import logging
import os
import signal
import sys
import time

from config import Config
from formatter import build_manage_keyboard
from ignored import add_ignored, load_ignored, remove_ignored
from models import Assignment, ChildProfile
from notifier import TelegramNotifier

logger = logging.getLogger("bot-listener")

POLL_TIMEOUT = 30
# File to store the latest scraped children data for the manage keyboard
_STATE_DIR = os.path.expanduser("~/.config/managebac-notifier")
_CHILDREN_CACHE = os.path.join(_STATE_DIR, "children_cache.json")


def setup_logging(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, "bot-listener.log")),
        ],
    )


def save_children_cache(children):
    """Save children + assignments to JSON for the bot listener to use"""
    data = []
    for child in children:
        data.append({
            "name": child.name,
            "managebac_id": child.managebac_id,
            "assignments": [
                {
                    "title": a.title,
                    "subject": a.subject,
                    "due_date": a.due_date.isoformat() if a.due_date else None,
                    "status": a.status,
                    "child_name": a.child_name,
                    "url": a.url,
                    "tags": a.tags,
                }
                for a in child.assignments
            ],
        })
    os.makedirs(os.path.dirname(_CHILDREN_CACHE), exist_ok=True)
    with open(_CHILDREN_CACHE, "w") as f:
        json.dump(data, f, ensure_ascii=False)


def load_children_cache():
    """Load children + assignments from the cache file"""
    if not os.path.exists(_CHILDREN_CACHE):
        return []
    with open(_CHILDREN_CACHE) as f:
        data = json.load(f)

    from datetime import datetime

    children = []
    for item in data:
        assignments = []
        for a in item["assignments"]:
            assignments.append(Assignment(
                title=a["title"],
                subject=a["subject"],
                due_date=datetime.fromisoformat(a["due_date"]) if a["due_date"] else None,
                status=a["status"],
                child_name=a["child_name"],
                url=a["url"],
                tags=a.get("tags", []),
            ))
        children.append(ChildProfile(
            name=item["name"],
            managebac_id=item["managebac_id"],
            assignments=assignments,
        ))
    return children


def handle_callback(notifier, callback_query):
    """Process a callback_query from an inline button press"""
    cb_id = callback_query["id"]
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    message_id = message.get("message_id")

    if data == "noop":
        notifier.answer_callback_query(cb_id)
        return

    if data == "manage":
        # Send a new manage message with toggle buttons
        children = load_children_cache()
        if not children:
            notifier.answer_callback_query(cb_id, "No cached data. Run the notifier first.")
            return

        text, keyboard = build_manage_keyboard(children)
        notifier.send_message(text, reply_markup=keyboard)
        notifier.answer_callback_query(cb_id)
        return

    if data == "done":
        # Delete the manage message
        try:
            notifier._call("deleteMessage", {
                "chat_id": notifier.chat_id,
                "message_id": message_id,
            })
        except Exception:
            pass
        notifier.answer_callback_query(cb_id, "Done")
        return

    if data.startswith("ign:"):
        task_id = data.split(":", 1)[1]
        ignored = load_ignored()

        if task_id in ignored:
            remove_ignored(task_id)
            notifier.answer_callback_query(cb_id, "Un-ignored")
            logger.info(f"Un-ignored task {task_id}")
        else:
            # Find task title from button text
            title = task_id
            for row in message.get("reply_markup", {}).get("inline_keyboard", []):
                for btn in row:
                    if btn.get("callback_data") == data:
                        title = btn.get("text", "").strip().lstrip("✓ ").strip()
                        break
            add_ignored(task_id, title)
            notifier.answer_callback_query(cb_id, f"Ignored")
            logger.info(f"Ignored task {task_id}: {title}")

        # Refresh the manage keyboard to update checkmarks
        children = load_children_cache()
        if children and message_id:
            text, keyboard = build_manage_keyboard(children)
            try:
                notifier.edit_message_text(message_id, text, reply_markup=keyboard)
            except Exception as e:
                logger.debug(f"Could not edit message: {e}")
        return

    notifier.answer_callback_query(cb_id, "Unknown action")


def run(config):
    """Main polling loop"""
    notifier = TelegramNotifier(config.bot_token, config.chat_id)
    offset = None
    running = True

    def stop(signum, frame):
        nonlocal running
        logger.info("Received stop signal, shutting down...")
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    logger.info("Bot listener started, polling for callbacks...")

    while running:
        try:
            updates = notifier.get_updates(offset=offset, timeout=POLL_TIMEOUT)
            for update in updates:
                update_id = update["update_id"]
                offset = update_id + 1

                if "callback_query" in update:
                    handle_callback(notifier, update["callback_query"])

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error during polling: {e}")
            time.sleep(5)

    notifier.close()
    logger.info("Bot listener stopped.")


def main():
    config = Config.load()
    setup_logging(config.log_dir)
    run(config)


if __name__ == "__main__":
    main()

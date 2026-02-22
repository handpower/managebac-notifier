"""Manage ignored task list stored in JSON"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.expanduser("~/.config/managebac-notifier")
_IGNORED_PATH = os.path.join(_CONFIG_DIR, "ignored.json")


def load_ignored(path=None):
    """Load ignored task IDs from JSON file. Returns a dict of {task_id: title}."""
    path = path or _IGNORED_PATH
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_ignored(ignored, path=None):
    """Save ignored task dict to JSON file."""
    path = path or _IGNORED_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(ignored, f, ensure_ascii=False, indent=2)


def add_ignored(task_id, title, path=None):
    """Add a task to the ignored list. Returns True if newly added."""
    ignored = load_ignored(path)
    if task_id in ignored:
        return False
    ignored[task_id] = title
    save_ignored(ignored, path)
    logger.info(f"Ignored task: {task_id} — {title}")
    return True


def remove_ignored(task_id, path=None):
    """Remove a task from the ignored list. Returns True if removed."""
    ignored = load_ignored(path)
    if task_id not in ignored:
        return False
    del ignored[task_id]
    save_ignored(ignored, path)
    logger.info(f"Un-ignored task: {task_id}")
    return True


def is_ignored(task_id, path=None):
    """Check if a task is ignored."""
    return task_id in load_ignored(path)

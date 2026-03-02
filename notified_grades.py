"""Track notified low grades to avoid duplicate alerts"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.expanduser("~/.config/managebac-notifier")
_NOTIFIED_PATH = os.path.join(_CONFIG_DIR, "notified_grades.json")


def load_notified(path=None):
    """Load notified grades. Returns dict of {"task_id:criteria": "description"}."""
    path = path or _NOTIFIED_PATH
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_notified(notified, path=None):
    """Save notified grades dict to JSON file."""
    path = path or _NOTIFIED_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(notified, f, ensure_ascii=False, indent=2)


def mark_notified(task_id, criteria, description="", path=None):
    """Mark a grade as notified. Returns True if newly added."""
    key = f"{task_id}:{criteria}"
    notified = load_notified(path)
    if key in notified:
        return False
    notified[key] = description
    save_notified(notified, path)
    logger.info(f"Marked grade notified: {key} — {description}")
    return True


def is_notified(task_id, criteria, path=None):
    """Check if a grade has already been notified."""
    key = f"{task_id}:{criteria}"
    return key in load_notified(path)

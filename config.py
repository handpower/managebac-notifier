"""YAML config loader for managebac-notifier"""

import json
import os
import stat
import subprocess
from datetime import date

import yaml


_CONFIG_DIR = os.path.expanduser("~/.config/managebac-notifier")
_CONFIG_PATH = os.path.join(_CONFIG_DIR, "config.yaml")
_TG_NOTIFY = os.path.expanduser("~/.local/bin/tg-notify")


class _Section:
    """Generic config section that allows attribute access"""

    def __init__(self, data):
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, _Section(value))
            else:
                setattr(self, key, value)

    def get(self, key, default=None):
        return getattr(self, key, default)


class Config:
    def __init__(self, data):
        self.managebac = _Section(data.get("managebac", {}))
        self.children = data.get("children", [])
        self._telegram = data.get("telegram", {})
        self._telegram_route = None
        self._line = data.get("line", {})
        self.upcoming_days = data.get("upcoming_days", 3)
        self.low_grade_threshold = data.get("low_grade_threshold", 3)
        self.ignore_tasks = [s.lower() for s in data.get("ignore_tasks", []) if s]
        overdue_since = data.get("overdue_since")
        self.overdue_since = date.fromisoformat(overdue_since) if overdue_since else None
        # LINE header colors keyed by child ID
        self.line_child_colors = {}
        for child in self.children:
            color = child.get("color") if isinstance(child, dict) else None
            child_id = child.get("id", "") if isinstance(child, dict) else ""
            if color and child_id:
                self.line_child_colors[child_id] = color

    @classmethod
    def load(cls, path=None):
        path = path or _CONFIG_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Config not found: {path}\n"
                f"Copy config.example.yaml to {_CONFIG_PATH} and fill in values."
            )
        _check_permissions(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(data)

    @property
    def base_url(self):
        return self.managebac.base_url

    @property
    def email(self):
        return self.managebac.email

    @property
    def password(self):
        return self.managebac.password

    @property
    def telegram_enabled(self):
        if self._telegram.get("tg_notify_topic"):
            return True
        return bool(self._telegram.get("bot_token_file") and self._telegram.get("chat_id"))

    @property
    def bot_token(self):
        token_file = os.path.expanduser(self._route()["token_file"])
        with open(token_file) as f:
            return f.read().strip()

    @property
    def chat_id(self):
        return self._route()["chat"]

    @property
    def thread_id(self):
        """Forum topic (message_thread_id) in a supergroup with Topics, or None."""
        return self._route()["thread"]

    def _route(self):
        """Where Telegram messages go: a tg-notify topic when configured, else the explicit keys.

        With `tg_notify_topic`, tg-notify's routes.toml stays the only place that
        knows the chat, thread and token file; this asks it once per Config.
        """
        if self._telegram_route is None:
            topic = self._telegram.get("tg_notify_topic")
            if topic:
                out = subprocess.run([_TG_NOTIFY, topic, "--route"], capture_output=True,
                                     text=True, check=True, timeout=30).stdout
                self._telegram_route = json.loads(out)
            else:
                self._telegram_route = {"chat": self._telegram["chat_id"],
                                        "thread": self._telegram.get("thread_id"),
                                        "token_file": self._telegram["bot_token_file"]}
        return self._telegram_route

    @property
    def line_enabled(self):
        return bool(self._line.get("channel_token_file") and self._line.get("group_id"))

    @property
    def line_channel_token(self):
        token_file = os.path.expanduser(self._line["channel_token_file"])
        with open(token_file) as f:
            return f.read().strip()

    @property
    def line_group_id(self):
        return self._line["group_id"]

    @property
    def log_dir(self):
        return os.path.join(_CONFIG_DIR, "logs")


def _check_permissions(path):
    """Warn if config file has overly permissive permissions"""
    mode = os.stat(path).st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        import warnings
        warnings.warn(
            f"Config file '{path}' has permissive permissions. "
            f"Run: chmod 600 {path}"
        )

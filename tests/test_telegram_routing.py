"""Where Telegram messages go: explicit config keys, or a tg-notify topic, plus forum threads."""

import json
import subprocess

import config as config_module
from config import Config
from notifier import TelegramNotifier


class _RouteRun:
    """Stands in for `tg-notify TOPIC --route` and records each call."""

    def __init__(self, route):
        self.calls = []
        self._stdout = json.dumps(route)

    def __call__(self, command, **kwargs):
        self.calls.append(command)
        return subprocess.CompletedProcess(command, 0, self._stdout, "")


def _sent_payloads(notifier, monkeypatch):
    payloads = []
    monkeypatch.setattr(notifier, "_call", lambda method, payload: payloads.append(payload) or {})
    return payloads


def test_sendMessage_withThread_targetsTheForumTopic(monkeypatch):
    with TelegramNotifier("t", -100, thread_id=4) as notifier:
        payloads = _sent_payloads(notifier, monkeypatch)
        notifier.send_message("hi", reply_markup={"inline_keyboard": []})
    assert payloads[0]["message_thread_id"] == 4
    assert payloads[0]["chat_id"] == -100


def test_sendMessage_withoutThread_omitsMessageThreadId(monkeypatch):
    with TelegramNotifier("t", -100) as notifier:
        payloads = _sent_payloads(notifier, monkeypatch)
        notifier.send_message("hi")
    assert "message_thread_id" not in payloads[0]


def test_config_tgNotifyTopic_takesTheRouteFromTgNotifyOnce(monkeypatch):
    run = _RouteRun({"topic": "school", "known": True, "chat": -1003818877083, "thread": 4,
                     "silent": False, "token_file": "~/.telegram-bot-token"})
    monkeypatch.setattr(config_module.subprocess, "run", run)
    cfg = Config({"telegram": {"tg_notify_topic": "school"}})
    assert cfg.telegram_enabled
    assert (cfg.chat_id, cfg.thread_id) == (-1003818877083, 4)
    assert run.calls == [[config_module._TG_NOTIFY, "school", "--route"]]


def test_config_explicitKeys_keepWorkingWithoutTgNotify(monkeypatch):
    run = _RouteRun({})
    monkeypatch.setattr(config_module.subprocess, "run", run)
    cfg = Config({"telegram": {"bot_token_file": "~/.telegram-bot-token", "chat_id": "123", "thread_id": 7}})
    assert cfg.telegram_enabled
    assert (cfg.chat_id, cfg.thread_id) == ("123", 7)
    assert run.calls == []


def test_config_explicitKeysWithoutThread_sendsToTheWholeChat():
    cfg = Config({"telegram": {"bot_token_file": "x", "chat_id": "123"}})
    assert cfg.thread_id is None


def test_config_noTelegramSection_isDisabled():
    assert not Config({}).telegram_enabled

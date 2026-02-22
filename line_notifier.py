"""LINE Messaging API push notification sender"""

import logging
from collections import defaultdict
from datetime import date

import httpx

from models import Assignment, ChildProfile

logger = logging.getLogger(__name__)

LINE_API_BASE = "https://api.line.me/v2/bot"

# Colors
COLOR_RED = "#DC3545"
COLOR_ORANGE = "#FD7E14"
COLOR_GRAY = "#6C757D"
COLOR_BLUE = "#0D6EFD"

DEFAULT_HEADER_COLOR = "#0D6EFD"


class LineNotifier:
    """Sync LINE Messaging API client for push messages"""

    def __init__(self, channel_token, group_id):
        self.channel_token = channel_token
        self.group_id = group_id
        self.client = httpx.Client(timeout=30.0)

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _push(self, messages):
        """Push messages to the configured group"""
        url = f"{LINE_API_BASE}/message/push"
        payload = {"to": self.group_id, "messages": messages}
        resp = self.client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {self.channel_token}"},
        )
        if not resp.is_success:
            logger.error(f"LINE API error: HTTP {resp.status_code}: {resp.text}")
            raise RuntimeError(f"LINE push failed: {resp.status_code}")
        logger.info("LINE message sent successfully")

    def send_flex_report(self, children, today=None, upcoming_days=3,
                         overdue_since=None, child_colors=None):
        """Send assignment report as Flex Message carousel"""
        today = today or date.today()
        bubbles = []
        for child in children:
            bubble = _build_child_bubble(child, today, upcoming_days,
                                         overdue_since, child_colors)
            if bubble:
                bubbles.append(bubble)

        if not bubbles:
            return

        # LINE carousel max 12 bubbles
        message = {
            "type": "flex",
            "altText": "ManageBac Assignment Report",
            "contents": {
                "type": "carousel",
                "contents": bubbles,
            },
        }
        self._push([message])


def _build_child_bubble(child, today, upcoming_days=3, overdue_since=None,
                        child_colors=None):
    """Build a Flex bubble for one child"""
    overdue = [a for a in child.assignments if a.is_overdue(today, since=overdue_since)]
    upcoming = [a for a in child.assignments if a.is_upcoming(today, upcoming_days)]

    if not overdue and not upcoming:
        return None

    child_short = child.name.split("(")[0].strip()
    header_color = (child_colors or {}).get(child.managebac_id, DEFAULT_HEADER_COLOR)

    body_contents = []

    if overdue:
        body_contents.append(_section_header(f"Overdue ({len(overdue)})", COLOR_RED))
        body_contents.extend(_task_list_by_subject(overdue))

    if upcoming:
        if overdue:
            body_contents.append({"type": "separator", "margin": "lg"})
        body_contents.append(_section_header(f"Upcoming ({len(upcoming)})", COLOR_ORANGE))
        body_contents.extend(_task_list_by_subject(upcoming))

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": child_short,
                    "weight": "bold",
                    "size": "lg",
                    "color": "#FFFFFF",
                },
            ],
            "backgroundColor": header_color,
            "paddingAll": "15px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "spacing": "sm",
            "paddingAll": "15px",
        },
    }


def _section_header(text, color):
    return {
        "type": "text",
        "text": text,
        "weight": "bold",
        "size": "md",
        "color": color,
        "margin": "lg",
    }


def _task_list_by_subject(assignments):
    """Group tasks by subject and return Flex components"""
    by_subject = defaultdict(list)
    for a in assignments:
        by_subject[a.subject or "Other"].append(a)

    components = []
    for subject, tasks in by_subject.items():
        components.append({
            "type": "text",
            "text": subject,
            "weight": "bold",
            "size": "sm",
            "color": "#333333",
            "margin": "md",
        })
        for a in tasks:
            tag = f" [{a.tags[0]}]" if a.tags else ""
            bullet = "\U0001f4cc" if "Summative" in a.tags else "•"
            components.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": bullet,
                        "size": "xs",
                        "flex": 0,
                        "gravity": "top",
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "flex": 1,
                        "contents": [
                            {
                                "type": "text",
                                "text": f"{a.title}{tag}",
                                "size": "xs",
                                "wrap": True,
                            },
                            {
                                "type": "text",
                                "text": a.due_date_str,
                                "size": "xxs",
                                "color": COLOR_GRAY,
                            },
                        ],
                    },
                ],
                "spacing": "sm",
                "margin": "sm",
            })
    return components

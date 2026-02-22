"""Data models for ManageBac assignments"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta


@dataclass
class Assignment:
    title: str
    subject: str
    due_date: datetime | None
    status: str  # "overdue", "not_submitted", "not_assessed", "pending", "submitted", "graded"
    child_name: str
    url: str = ""
    tags: list[str] = field(default_factory=list)

    _DONE_STATUSES = ("submitted", "not_assessed", "graded")

    @property
    def _due_date_only(self) -> date | None:
        return self.due_date.date() if self.due_date else None

    def is_overdue(self, today: date | None = None, since: date | None = None) -> bool:
        today = today or date.today()
        if self.status in self._DONE_STATUSES:
            return False
        if since and self._due_date_only is not None and self._due_date_only < since:
            return False
        if self.status == "overdue":
            return True
        return self._due_date_only is not None and self._due_date_only < today

    def is_upcoming(self, today: date | None = None, days: int = 3) -> bool:
        today = today or date.today()
        if self.status in self._DONE_STATUSES:
            return False
        if self.status == "overdue":
            return False
        if self._due_date_only is None:
            return False
        return today <= self._due_date_only <= today + timedelta(days=days)

    @property
    def task_id(self) -> str:
        """Extract task ID from URL like /classes/123/tasks/456?child=789"""
        match = re.search(r"/tasks/(\d+)", self.url)
        return match.group(1) if match else ""

    @property
    def due_date_str(self) -> str:
        if self.due_date is None:
            return "no date"
        return self.due_date.strftime("%-m/%-d %-H:%M")

    @property
    def tags_str(self) -> str:
        if not self.tags:
            return ""
        return " ".join(f"[{t}]" for t in self.tags)


@dataclass
class ChildProfile:
    name: str
    managebac_id: str = ""
    assignments: list[Assignment] = field(default_factory=list)

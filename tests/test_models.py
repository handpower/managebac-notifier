from datetime import date, datetime

from models import Assignment


class TestAssignment:
    def test_is_overdue_by_date(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 20, 23, 55), "pending", "Alice")
        assert a.is_overdue(today) is True

    def test_is_overdue_by_status(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 23, 8, 0), "overdue", "Alice")
        assert a.is_overdue(today) is True

    def test_not_overdue_if_submitted(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 20, 23, 55), "submitted", "Alice")
        assert a.is_overdue(today) is False

    def test_not_overdue_if_graded(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 20, 23, 55), "graded", "Alice")
        assert a.is_overdue(today) is False

    def test_is_upcoming_within_3_days(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 24, 11, 55), "pending", "Alice")
        assert a.is_upcoming(today, days=3) is True

    def test_is_upcoming_today(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 22, 8, 0), "pending", "Alice")
        assert a.is_upcoming(today, days=3) is True

    def test_not_upcoming_if_too_far(self, today):
        a = Assignment("hw", "Math", datetime(2026, 3, 1, 23, 55), "pending", "Alice")
        assert a.is_upcoming(today, days=3) is False

    def test_not_upcoming_if_submitted(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 23, 8, 0), "submitted", "Alice")
        assert a.is_upcoming(today, days=3) is False

    def test_not_upcoming_if_overdue(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 20, 23, 55), "pending", "Alice")
        assert a.is_upcoming(today, days=3) is False

    def test_due_date_str_with_time(self):
        a = Assignment("hw", "Math", datetime(2026, 2, 5, 11, 55), "pending", "Alice")
        assert a.due_date_str == "2/5 11:55"

    def test_due_date_str_none(self):
        a = Assignment("hw", "Math", None, "pending", "Alice")
        assert a.due_date_str == "no date"

    def test_tags_str(self):
        a = Assignment("hw", "Math", None, "pending", "Alice", tags=["Summative", "Classwork"])
        assert a.tags_str == "[Summative] [Classwork]"

    def test_tags_str_empty(self):
        a = Assignment("hw", "Math", None, "pending", "Alice")
        assert a.tags_str == ""

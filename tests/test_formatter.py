from datetime import date, datetime

from formatter import format_report, format_report_plain
from models import Assignment, ChildProfile


class TestFormatReport:
    def test_full_report(self, sample_children, today):
        report = format_report(sample_children, today)
        assert "ManageBac Assignment Report" in report
        assert "2026-02-22" in report
        assert "Alice" in report
        assert "Bob" in report
        assert "Overdue" in report
        assert "Upcoming" in report
        assert "Worksheet Ch.5" in report
        assert "Lab Report" in report
        assert "No overdue or upcoming" in report

    def test_grouped_by_subject(self, today):
        children = [
            ChildProfile(
                name="Alice",
                managebac_id="1",
                assignments=[
                    Assignment("HW1", "Math", datetime(2026, 2, 20, 23, 55), "overdue", "Alice"),
                    Assignment("HW2", "Math", datetime(2026, 2, 19, 23, 55), "overdue", "Alice"),
                    Assignment("Essay", "English", datetime(2026, 2, 18, 23, 55), "overdue", "Alice"),
                ],
            )
        ]
        report = format_report(children, today)
        assert "<b>Math</b>" in report
        assert "<b>English</b>" in report
        math_pos = report.index("<b>Math</b>")
        hw1_pos = report.index("HW1")
        hw2_pos = report.index("HW2")
        english_pos = report.index("<b>English</b>")
        assert math_pos < hw1_pos < hw2_pos < english_pos

    def test_no_assignments(self, today):
        children = [ChildProfile(name="Alice", managebac_id="1")]
        report = format_report(children, today)
        assert "No overdue or upcoming" in report

    def test_only_overdue(self, today):
        children = [
            ChildProfile(
                name="Alice",
                managebac_id="1",
                assignments=[
                    Assignment("hw", "Math", datetime(2026, 2, 20, 23, 55), "overdue", "Alice"),
                ],
            )
        ]
        report = format_report(children, today)
        assert "Overdue (1)" in report
        assert "Upcoming" not in report

    def test_excludes_submitted(self, sample_children, today):
        report = format_report(sample_children, today)
        assert "Book Report" not in report

    def test_excludes_far_future(self, sample_children, today):
        report = format_report(sample_children, today)
        assert "History Reading" not in report

    def test_includes_url_as_link(self, sample_children, today):
        report = format_report(sample_children, today)
        assert 'href="https://school.managebac.com/tasks/1"' in report

    def test_includes_tags(self, sample_children, today):
        report = format_report(sample_children, today)
        assert "[Summative]" in report
        assert "[Formative]" in report

    def test_includes_time_in_due_date(self, sample_children, today):
        report = format_report(sample_children, today)
        assert "2/24 11:55" in report

    def test_upcoming_days_parameter(self, sample_children, today):
        """Tasks beyond default 3 days but within custom upcoming_days should appear"""
        report_3d = format_report(sample_children, today, upcoming_days=3)
        assert "History Reading" not in report_3d

        report_8d = format_report(sample_children, today, upcoming_days=8)
        assert "History Reading" in report_8d

    def test_upcoming_days_plain(self, sample_children, today):
        """Plain text formatter should also respect upcoming_days"""
        report_3d = format_report_plain(sample_children, today, upcoming_days=3)
        assert "History Reading" not in report_3d

        report_8d = format_report_plain(sample_children, today, upcoming_days=8)
        assert "History Reading" in report_8d

    def test_overdue_since_filters_old_tasks(self, today):
        """Tasks before overdue_since should not appear in overdue"""
        children = [
            ChildProfile(
                name="Alice",
                managebac_id="1",
                assignments=[
                    Assignment("Old HW", "Math", datetime(2026, 1, 15, 23, 55),
                               "pending", "Alice"),
                    Assignment("Recent HW", "Math", datetime(2026, 2, 10, 23, 55),
                               "pending", "Alice"),
                ],
            )
        ]
        since = date(2026, 1, 24)
        report = format_report(children, today, overdue_since=since)
        assert "Old HW" not in report
        assert "Recent HW" in report

        plain = format_report_plain(children, today, overdue_since=since)
        assert "Old HW" not in plain
        assert "Recent HW" in plain

    def test_summative_pin_emoji(self, today):
        """Summative tasks should have pin emoji, others should not"""
        children = [
            ChildProfile(
                name="Alice",
                managebac_id="1",
                assignments=[
                    Assignment("Quiz", "Math", datetime(2026, 2, 20, 23, 55),
                               "overdue", "Alice", tags=["Summative"]),
                    Assignment("Homework", "Math", datetime(2026, 2, 20, 23, 55),
                               "overdue", "Alice", tags=["Formative"]),
                ],
            )
        ]
        report = format_report(children, today)
        assert "\U0001f4cc Quiz" in report
        assert "\U0001f4cc Homework" not in report

        plain = format_report_plain(children, today)
        assert "\U0001f4cc Quiz" in plain
        assert "\U0001f4cc Homework" not in plain

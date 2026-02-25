from datetime import date, datetime

from formatter import format_report, format_report_plain, _relative_due_label
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
        # Urgent summary should appear at top
        assert "需要注意" in report

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
        # Check ordering in the detail section (after the summary separator)
        detail_start = report.index("Overdue")
        detail = report[detail_start:]
        assert "<b>Math</b>" in detail
        assert "<b>English</b>" in detail
        math_pos = detail.index("<b>Math</b>")
        hw1_pos = detail.index("HW1")
        hw2_pos = detail.index("HW2")
        english_pos = detail.index("<b>English</b>")
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


class TestUrgentSummary:
    def test_summary_includes_overdue_and_due_soon(self, today):
        """Summary should list overdue items and items due within 48 hours"""
        children = [
            ChildProfile(
                name="Alice",
                managebac_id="1",
                assignments=[
                    Assignment("Overdue HW", "Math", datetime(2026, 2, 20, 23, 55),
                               "overdue", "Alice"),
                    Assignment("Tomorrow HW", "Science", datetime(2026, 2, 23, 11, 0),
                               "pending", "Alice"),
                    Assignment("Far Away HW", "English", datetime(2026, 2, 28, 23, 55),
                               "pending", "Alice"),
                ],
            )
        ]
        report = format_report(children, today)
        assert "需要注意 (2)" in report
        assert "[逾期]" in report
        assert "Overdue HW" in report
        assert "[明天]" in report
        assert "Tomorrow HW" in report
        # Far away should NOT be in summary
        summary_end = report.index("─────")
        assert "Far Away HW" not in report[:summary_end]

    def test_summary_appears_before_details(self, today):
        """Urgent summary should appear before the per-child detail sections"""
        children = [
            ChildProfile(
                name="Alice",
                managebac_id="1",
                assignments=[
                    Assignment("hw", "Math", datetime(2026, 2, 20, 23, 55),
                               "overdue", "Alice"),
                ],
            )
        ]
        report = format_report(children, today)
        summary_pos = report.index("需要注意")
        detail_pos = report.index("Overdue (1)")
        assert summary_pos < detail_pos

    def test_summary_not_shown_when_nothing_urgent(self, today):
        """No summary if no overdue and no due-soon items"""
        children = [
            ChildProfile(
                name="Alice",
                managebac_id="1",
                assignments=[
                    Assignment("Far HW", "Math", datetime(2026, 2, 28, 23, 55),
                               "pending", "Alice"),
                ],
            )
        ]
        report = format_report(children, today, upcoming_days=7)
        assert "需要注意" not in report
        assert "─────" not in report

    def test_summary_relative_labels(self, today):
        """Check correct labels: 今天, 明天, 後天"""
        children = [
            ChildProfile(
                name="Alice",
                managebac_id="1",
                assignments=[
                    Assignment("Today HW", "Math", datetime(2026, 2, 22, 23, 55),
                               "pending", "Alice"),
                    Assignment("Tomorrow HW", "Math", datetime(2026, 2, 23, 11, 0),
                               "pending", "Alice"),
                    Assignment("Day After HW", "Math", datetime(2026, 2, 24, 11, 0),
                               "pending", "Alice"),
                ],
            )
        ]
        report = format_report(children, today)
        assert "[今天]" in report
        assert "[明天]" in report
        assert "[後天]" in report

    def test_summary_respects_overdue_since(self, today):
        """Old overdue tasks filtered by overdue_since should not appear in summary"""
        children = [
            ChildProfile(
                name="Alice",
                managebac_id="1",
                assignments=[
                    Assignment("Old HW", "Math", datetime(2026, 1, 10, 23, 55),
                               "pending", "Alice"),
                    Assignment("Recent HW", "Math", datetime(2026, 2, 15, 23, 55),
                               "pending", "Alice"),
                ],
            )
        ]
        since = date(2026, 1, 24)
        report = format_report(children, today, overdue_since=since)
        assert "Old HW" not in report
        assert "Recent HW" in report

    def test_summary_multi_child(self, today):
        """Summary should show child name prefix for each item"""
        children = [
            ChildProfile(
                name="Alice",
                managebac_id="1",
                assignments=[
                    Assignment("HW A", "Math", datetime(2026, 2, 20, 23, 55),
                               "overdue", "Alice"),
                ],
            ),
            ChildProfile(
                name="Bob",
                managebac_id="2",
                assignments=[
                    Assignment("HW B", "Science", datetime(2026, 2, 23, 11, 0),
                               "pending", "Bob"),
                ],
            ),
        ]
        report = format_report(children, today)
        assert "需要注意 (2)" in report
        assert "[Alice]" in report
        assert "[Bob]" in report

    def test_summary_summative_pin(self, today):
        """Summative items in summary should have pin emoji"""
        children = [
            ChildProfile(
                name="Alice",
                managebac_id="1",
                assignments=[
                    Assignment("Big Exam", "Math", datetime(2026, 2, 23, 23, 55),
                               "pending", "Alice", tags=["Summative"]),
                ],
            )
        ]
        report = format_report(children, today)
        summary_end = report.index("─────")
        summary = report[:summary_end]
        assert "\U0001f4cc" in summary
        assert "Big Exam" in summary


class TestRelativeDueLabel:
    def test_today(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 22, 23, 55), "pending", "Alice")
        assert _relative_due_label(a, today) == "今天"

    def test_tomorrow(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 23, 10, 0), "pending", "Alice")
        assert _relative_due_label(a, today) == "明天"

    def test_day_after(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 24, 10, 0), "pending", "Alice")
        assert _relative_due_label(a, today) == "後天"

    def test_no_label_for_far_date(self, today):
        a = Assignment("hw", "Math", datetime(2026, 2, 28, 10, 0), "pending", "Alice")
        assert _relative_due_label(a, today) == ""

    def test_no_date(self, today):
        a = Assignment("hw", "Math", None, "pending", "Alice")
        assert _relative_due_label(a, today) == ""

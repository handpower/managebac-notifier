"""Format assignments into Telegram HTML message, grouped by subject"""

from collections import defaultdict
from datetime import date

from ignored import load_ignored
from models import Assignment, ChildProfile

WEEKDAY_MAP = {0: "一", 1: "二", 2: "三", 3: "四", 4: "五", 5: "六", 6: "日"}

# Single button under the daily report
MANAGE_BUTTON = {"inline_keyboard": [[{
    "text": "Manage Ignore List",
    "callback_data": "manage",
}]]}


def format_report(children: list[ChildProfile], today: date | None = None) -> str:
    today = today or date.today()
    weekday = WEEKDAY_MAP[today.weekday()]
    date_str = today.strftime(f"%Y-%m-%d ({weekday})")

    lines = [
        f"<b>ManageBac Assignment Report</b>",
        f"<b>{date_str}</b>",
    ]

    for child in children:
        overdue = [a for a in child.assignments if a.is_overdue(today)]
        upcoming = [a for a in child.assignments if a.is_upcoming(today)]

        lines.append(f"\n<b>{child.name}</b>")

        if not overdue and not upcoming:
            lines.append("No overdue or upcoming assignments.")
            continue

        if overdue:
            lines.append(f"\n<b>Overdue ({len(overdue)}):</b>")
            lines.extend(_format_by_subject(overdue))

        if upcoming:
            lines.append(f"\n<b>Upcoming ({len(upcoming)}):</b>")
            lines.extend(_format_by_subject(upcoming))

    return "\n".join(lines)


def build_manage_keyboard(children: list[ChildProfile], today: date | None = None):
    """Build the interactive 'manage' message with toggle buttons per task.

    Returns (text, reply_markup) tuple.
    Tasks already in ignored.json show a checkmark.
    """
    today = today or date.today()
    ignored = load_ignored()
    buttons = []

    for child in children:
        all_tasks = [
            a for a in child.assignments
            if a.is_overdue(today) or a.is_upcoming(today)
        ]
        if not all_tasks:
            continue

        child_short = child.name.split("(")[0].strip()
        # Add a section header as a disabled-looking button
        buttons.append([{
            "text": f"--- {child_short} ---",
            "callback_data": "noop",
        }])

        for a in all_tasks:
            if not a.task_id:
                continue
            is_ignored = a.task_id in ignored
            prefix = "✓ " if is_ignored else "    "
            label = f"{prefix}{a.subject[:10]}: {a.title[:28]}"
            buttons.append([{
                "text": label,
                "callback_data": f"ign:{a.task_id}",
            }])

    # Close button
    buttons.append([{"text": "Done", "callback_data": "done"}])

    text = (
        "<b>Manage Ignore List</b>\n\n"
        "Tap a task to toggle ignore.\n"
        "✓ = ignored (won't appear in daily report)"
    )
    return text, {"inline_keyboard": buttons}


def format_report_plain(children: list[ChildProfile], today: date | None = None) -> str:
    """Format report as plain text (for LINE)"""
    today = today or date.today()
    weekday = WEEKDAY_MAP[today.weekday()]
    date_str = today.strftime(f"%Y-%m-%d ({weekday})")

    lines = [
        "ManageBac Assignment Report",
        date_str,
    ]

    for child in children:
        overdue = [a for a in child.assignments if a.is_overdue(today)]
        upcoming = [a for a in child.assignments if a.is_upcoming(today)]

        lines.append(f"\n{child.name}")

        if not overdue and not upcoming:
            lines.append("No overdue or upcoming assignments.")
            continue

        if overdue:
            lines.append(f"\nOverdue ({len(overdue)}):")
            lines.extend(_format_by_subject_plain(overdue))

        if upcoming:
            lines.append(f"\nUpcoming ({len(upcoming)}):")
            lines.extend(_format_by_subject_plain(upcoming))

    return "\n".join(lines)


def _format_by_subject_plain(assignments: list[Assignment]) -> list[str]:
    """Group assignments by subject and format as plain text"""
    by_subject = defaultdict(list)
    for a in assignments:
        subject = a.subject or "Other"
        by_subject[subject].append(a)

    lines = []
    for subject, tasks in by_subject.items():
        lines.append(f"  [{subject}]")
        for a in tasks:
            # Only show first tag (Summative/Formative) for brevity
            tag = f" [{a.tags[0]}]" if a.tags else ""
            lines.append(f"    • {a.title}{tag} ({a.due_date_str})")
    return lines


def _format_by_subject(assignments: list[Assignment]) -> list[str]:
    """Group assignments by subject and format each group"""
    by_subject = defaultdict(list)
    for a in assignments:
        subject = a.subject or "Other"
        by_subject[subject].append(a)

    lines = []
    for subject, tasks in by_subject.items():
        lines.append(f"  <b>{subject}</b>")
        for a in tasks:
            title = f'<a href="{a.url}">{a.title}</a>' if a.url else a.title
            tags = f" {a.tags_str}" if a.tags_str else ""
            lines.append(f"    • {title}{tags} (due {a.due_date_str})")
    return lines

import sys
import os
from datetime import date, datetime

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Assignment, ChildProfile


@pytest.fixture
def today():
    return date(2026, 2, 22)


@pytest.fixture
def sample_assignments(today):
    return [
        Assignment(
            title="Worksheet Ch.5",
            subject="Math",
            due_date=datetime(2026, 2, 20, 23, 55),
            status="pending",
            child_name="Alice",
            url="https://school.managebac.com/tasks/1",
            tags=["Summative"],
        ),
        Assignment(
            title="Essay Draft",
            subject="English",
            due_date=datetime(2026, 2, 19, 8, 0),
            status="overdue",
            child_name="Alice",
            url="https://school.managebac.com/tasks/2",
            tags=["Formative"],
        ),
        Assignment(
            title="Lab Report",
            subject="Science",
            due_date=datetime(2026, 2, 24, 11, 55),
            status="pending",
            child_name="Alice",
            url="https://school.managebac.com/tasks/3",
            tags=["Assignment"],
        ),
        Assignment(
            title="History Reading",
            subject="History",
            due_date=datetime(2026, 3, 1, 23, 55),
            status="pending",
            child_name="Alice",
        ),
        Assignment(
            title="Book Report",
            subject="English",
            due_date=datetime(2026, 2, 18, 23, 55),
            status="submitted",
            child_name="Alice",
        ),
    ]


@pytest.fixture
def sample_children(sample_assignments):
    return [
        ChildProfile(
            name="Alice",
            managebac_id="111",
            assignments=sample_assignments,
        ),
        ChildProfile(
            name="Bob",
            managebac_id="222",
            assignments=[],
        ),
    ]

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup

from scraper import ManageBacClient

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")


class TestParseGrades:
    def _parse_fixture(self, filename="past_tasks.html"):
        path = os.path.join(FIXTURES_DIR, filename)
        with open(path) as f:
            html = f.read()
        soup = BeautifulSoup(html, "lxml")
        client = ManageBacClient("https://example.com", "x", "x")
        return client._parse_tasks(soup, "TestChild", "past")

    def test_graded_tasks_have_grades(self):
        tasks = self._parse_fixture()
        graded = [t for t in tasks if t.grades]
        assert len(graded) >= 2  # at least the two criteria-scored tasks in fixture

    def test_grade_fields(self):
        tasks = self._parse_fixture()
        graded = [t for t in tasks if t.grades]
        g = graded[0].grades[0]
        assert "criteria" in g
        assert "criteria_name" in g
        assert "score" in g
        assert "max_score" in g
        assert isinstance(g["score"], int)
        assert isinstance(g["max_score"], int)

    def test_specific_grade_values(self):
        """Verify actual values from the fixture: U4 Reflection Journal 02 has D:4/8"""
        tasks = self._parse_fixture()
        journal02 = [t for t in tasks if "Reflection Journal 02" in t.title]
        assert len(journal02) == 1
        assert len(journal02[0].grades) == 1
        g = journal02[0].grades[0]
        assert g["criteria"] == "D"
        assert g["criteria_name"] == "D: Evaluating"
        assert g["score"] == 4
        assert g["max_score"] == 8

    def test_ungraded_tasks_have_empty_grades(self):
        tasks = self._parse_fixture()
        ungraded = [t for t in tasks if not t.grades]
        assert len(ungraded) > 0  # fixture has tasks without criteria scores

    def test_status_graded_for_criteria_tasks(self):
        tasks = self._parse_fixture()
        graded = [t for t in tasks if t.grades]
        for t in graded:
            assert t.status == "graded"

"""ManageBac web scraper — login and assignment extraction"""

import logging
import os
import re
from datetime import date, datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from models import Assignment, ChildProfile

logger = logging.getLogger(__name__)

CURRENT_YEAR = date.today().year


class LoginError(Exception):
    pass


class ScrapingError(Exception):
    pass


class ManageBacClient:
    """HTTP client for ManageBac parent portal"""

    def __init__(self, base_url, email, password):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
            },
        )
        self._logged_in = False

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def login(self):
        """Login to ManageBac and establish session cookies"""
        login_url = f"{self.base_url}/login"
        logger.info(f"Fetching login page: {login_url}")

        resp = self.client.get(login_url)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        token_input = soup.find("input", {"name": "authenticity_token"})
        if not token_input:
            raise LoginError("Could not find CSRF token on login page")
        csrf_token = token_input["value"]

        logger.info(f"Logging in as {self.email}")
        login_resp = self.client.post(
            f"{self.base_url}/sessions",
            data={
                "authenticity_token": csrf_token,
                "login": self.email,
                "password": self.password,
                "remember_me": "1",
                "commit": "Sign in",
            },
        )
        login_resp.raise_for_status()

        if "/login" in str(login_resp.url):
            raise LoginError(
                "Login failed — redirected back to login page. Check credentials."
            )

        self._logged_in = True
        logger.info(f"Login successful, redirected to: {login_resp.url}")
        return login_resp

    def explore(self, output_dir):
        """Explore the parent portal and save HTML pages for analysis"""
        if not self._logged_in:
            self.login()

        os.makedirs(output_dir, exist_ok=True)
        visited = {}

        # 1. Save dashboard / landing page
        dashboard_resp = self.client.get(f"{self.base_url}/parent")
        if dashboard_resp.status_code == 404:
            dashboard_resp = self.client.get(self.base_url)
        self._save_page(dashboard_resp, output_dir, "dashboard")
        visited["dashboard"] = str(dashboard_resp.url)

        # 2. Find links to child profiles / assignments
        soup = BeautifulSoup(dashboard_resp.text, "lxml")
        self._print_page_summary(soup, "Dashboard")

        # Look for common ManageBac parent portal patterns
        explore_paths = [
            "/parent",
            "/parent/tasks",
            "/parent/classes",
            "/parent/attendance",
            "/parent/calendar",
        ]

        # Also find links in the page that look relevant
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if any(kw in href for kw in [
                "task", "assignment", "class", "student", "child",
                "deadline", "calendar", "parent",
            ]):
                if href.startswith("/"):
                    explore_paths.append(href)

        # Deduplicate
        explore_paths = list(dict.fromkeys(explore_paths))

        for path in explore_paths:
            url = f"{self.base_url}{path}" if path.startswith("/") else path
            name = path.strip("/").replace("/", "_") or "root"
            if name in visited:
                continue
            try:
                logger.info(f"Exploring: {url}")
                resp = self.client.get(url)
                if resp.status_code == 200:
                    self._save_page(resp, output_dir, name)
                    visited[name] = str(resp.url)
                    page_soup = BeautifulSoup(resp.text, "lxml")
                    self._print_page_summary(page_soup, name)
                else:
                    logger.info(f"  -> {resp.status_code}")
            except Exception as e:
                logger.warning(f"  -> Error: {e}")

        print(f"\n{'='*60}")
        print(f"Saved {len(visited)} pages to {output_dir}/")
        for name, url in visited.items():
            print(f"  {name}.html -> {url}")
        print(f"{'='*60}")

        return visited

    def get_children(self, dashboard_html=None):
        """Parse parent dashboard to discover children from child switcher dropdown"""
        if dashboard_html is None:
            if not self._logged_in:
                self.login()
            resp = self.client.get(f"{self.base_url}/parent")
            dashboard_html = resp.text

        soup = BeautifulSoup(dashboard_html, "lxml")
        children = []

        # ManageBac uses PUT /parent/child/{id} links in the child switcher dropdown
        for link in soup.select("a[href*='/parent/child/']"):
            href = link["href"]
            match = re.search(r"/parent/child/(\d+)", href)
            if not match:
                continue
            child_id = match.group(1)
            if child_id in [c.managebac_id for c in children]:
                continue

            # Name is in <div class='fw-semibold'> inside the link
            name_el = link.select_one(".fw-semibold")
            name = name_el.get_text(strip=True) if name_el else link.get_text(strip=True)
            children.append(ChildProfile(name=name, managebac_id=child_id))

        logger.info(f"Found {len(children)} children: {[c.name for c in children]}")
        return children

    def _switch_child(self, child_id):
        """Switch active child via PUT request"""
        logger.info(f"Switching to child: {child_id}")

        # Get CSRF token from a page first
        resp = self.client.get(f"{self.base_url}/parent")
        soup = BeautifulSoup(resp.text, "lxml")
        meta_token = soup.find("meta", {"name": "csrf-token"})
        csrf_token = meta_token["content"] if meta_token else ""

        switch_resp = self.client.put(
            f"{self.base_url}/parent/child/{child_id}",
            headers={
                "X-CSRF-Token": csrf_token,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "text/javascript, application/javascript",
            },
        )
        switch_resp.raise_for_status()
        logger.info(f"Switched to child {child_id}")

    def get_assignments(self, child, upcoming_days=3):
        """Fetch upcoming and overdue assignments for a specific child"""
        if not self._logged_in:
            self.login()

        self._switch_child(child.managebac_id)

        assignments = []

        # Fetch overdue tasks
        overdue_url = f"{self.base_url}/parent/tasks_and_deadlines?view=overdue"
        logger.info(f"Fetching overdue tasks: {overdue_url}")
        resp = self.client.get(overdue_url)
        resp.raise_for_status()
        overdue_soup = BeautifulSoup(resp.text, "lxml")
        overdue_tasks = self._parse_tasks(overdue_soup, child.name, "overdue")
        assignments.extend(overdue_tasks)

        # Fetch upcoming tasks
        upcoming_url = f"{self.base_url}/parent/tasks_and_deadlines?view=upcoming"
        logger.info(f"Fetching upcoming tasks: {upcoming_url}")
        resp = self.client.get(upcoming_url)
        resp.raise_for_status()
        upcoming_soup = BeautifulSoup(resp.text, "lxml")
        upcoming_tasks = self._parse_tasks(upcoming_soup, child.name, "upcoming")

        # Filter upcoming to only include tasks within upcoming_days
        today = date.today()
        for task in upcoming_tasks:
            if task.is_upcoming(today, upcoming_days):
                assignments.append(task)

        logger.info(
            f"Found {len(assignments)} relevant assignments for {child.name} "
            f"({len(overdue_tasks)} overdue, "
            f"{len([a for a in assignments if a.is_upcoming(today, upcoming_days)])} upcoming)"
        )
        return assignments

    def _parse_tasks(self, soup, child_name, view):
        """Parse task tiles from the tasks_and_deadlines page"""
        tasks = []
        task_container = soup.select_one(".js-tasks")
        if not task_container:
            logger.warning("Could not find task container (.js-tasks)")
            return tasks

        for tile in task_container.select(".f-tile--inline"):
            task = self._parse_task_tile(tile, child_name, view)
            if task:
                tasks.append(task)

        return tasks

    def _parse_task_tile(self, tile, child_name, view):
        """Parse a single f-tile--inline element into an Assignment"""
        # Title and URL
        title_link = tile.select_one("a.f-tile__title-link")
        if not title_link:
            return None
        title = title_link.get_text(strip=True)
        url = urljoin(self.base_url, title_link.get("href", ""))

        # Subject/class name
        subject = ""
        class_link = tile.select_one("a.f-truncate-item.link-dark")
        if class_link:
            subject = class_link.get_text(strip=True)
            # Strip common prefixes for brevity
            subject = re.sub(r"^IB MYP\s+IB MYP\s+", "", subject)
            subject = re.sub(r"^IB MYP\s+", "", subject)
            subject = re.sub(r"\s*\(Grade \d+\)\s*[A-Z]?$", "", subject)

        # Tags — badge-label spans (e.g., Summative, Formative, Classwork)
        tags = []
        for badge in tile.select("span.badge-label"):
            tag_text = badge.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)

        # Due date — text next to clock icon in description
        due_date = None
        desc_div = tile.select_one(".f-tile__description")
        if desc_div:
            # Find spans that contain date text (next to clock SVG)
            for span in desc_div.find_all("span", recursive=True):
                span_text = span.get_text(strip=True)
                parsed = self._parse_due_date(span_text, view)
                if parsed:
                    due_date = parsed
                    break

        # Status — from f-task-score CSS class
        status = "pending"
        score_div = tile.select_one("[class*='f-task-score--']")
        if score_div:
            classes = " ".join(score_div.get("class", []))
            if "not-submitted" in classes:
                status = "not_submitted"
            elif "not-assessed" in classes:
                status = "not_assessed"
            elif "submitted" in classes:
                status = "submitted"
            elif any(c in classes for c in ("graded", "assessed", "criteria", "assessment")):
                status = "graded"

        # Also check the text inside score div
        score_text_el = tile.select_one(".f-task-score__body p")
        if score_text_el:
            score_text = score_text_el.get_text(strip=True).lower()
            if "not submitted" in score_text:
                status = "not_submitted"
            elif "not assessed" in score_text:
                status = "not_assessed"
            elif "submitted" in score_text:
                status = "submitted"

        # For overdue view, mark as overdue if not submitted
        if view == "overdue" and status in ("not_submitted", "pending"):
            status = "overdue"

        return Assignment(
            title=title,
            subject=subject,
            due_date=due_date,
            status=status,
            child_name=child_name,
            url=url,
            tags=tags,
        )

    def _parse_due_date(self, text, view=None):
        """Parse datetime from ManageBac format like 'Feb 22, 11:55 PM' or 'Mar 3, 8:00 AM'

        ManageBac doesn't include the year. We default to the current year,
        but for overdue tasks a future date means it's actually last year
        (e.g., "Dec 30" on the overdue page in Feb 2026 → Dec 30, 2025).
        """
        if not text:
            return None
        parsed = None
        # Try full datetime first: "Feb 22, 11:55 PM"
        match = re.match(r"([A-Z][a-z]{2})\s+(\d{1,2}),\s*(\d{1,2}:\d{2}\s*[AP]M)", text)
        if match:
            month_str, day_str, time_str = match.group(1), match.group(2), match.group(3)
            try:
                parsed = datetime.strptime(
                    f"{month_str} {day_str} {CURRENT_YEAR} {time_str}",
                    "%b %d %Y %I:%M %p",
                )
            except ValueError:
                pass
        if not parsed:
            # Fallback: date only "Feb 22"
            match = re.match(r"([A-Z][a-z]{2})\s+(\d{1,2})", text)
            if not match:
                return None
            month_str, day_str = match.group(1), match.group(2)
            try:
                parsed = datetime.strptime(f"{month_str} {day_str} {CURRENT_YEAR}", "%b %d %Y")
            except ValueError:
                return None
        # Overdue tasks can't be in the future — adjust year if needed
        if parsed and view == "overdue" and parsed.date() > date.today():
            parsed = parsed.replace(year=CURRENT_YEAR - 1)
        return parsed

    def _parse_date(self, date_str):
        """Try multiple date formats"""
        if not date_str:
            return None
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%b %d, %Y",
            "%B %d, %Y",
            "%d %b %Y",
            "%d %B %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        logger.debug(f"Could not parse date: {date_str}")
        return None

    def _save_page(self, resp, output_dir, name):
        """Save response HTML to file"""
        filepath = os.path.join(output_dir, f"{name}.html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(resp.text)
        logger.info(f"Saved: {filepath} ({len(resp.text)} bytes)")

    def _print_page_summary(self, soup, label):
        """Print a summary of a page for exploration"""
        title = soup.title.string if soup.title else "(no title)"
        print(f"\n--- {label} ---")
        print(f"Title: {title}")

        # Print key navigation links
        nav_links = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)[:60]
            if href.startswith("/") and text and not href.startswith("/assets"):
                nav_links.append((href, text))

        # Deduplicate and show first 20
        seen = set()
        for href, text in nav_links:
            if href not in seen:
                seen.add(href)
                print(f"  {href} -> {text}")
            if len(seen) >= 20:
                remaining = len(nav_links) - len(seen)
                if remaining > 0:
                    print(f"  ... and {remaining} more links")
                break

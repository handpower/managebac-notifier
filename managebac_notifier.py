#!/usr/bin/env python
"""ManageBac assignment notifier — daily Telegram notification"""

import argparse
import logging
import os
import sys
from datetime import date

from config import Config
from bot_listener import save_children_cache
from formatter import MANAGE_BUTTON, format_report, format_report_plain
from ignored import load_ignored
from line_notifier import LineNotifier
from models import ChildProfile
from notifier import TelegramNotifier
from scraper import LoginError, ManageBacClient, ScrapingError

logger = logging.getLogger("managebac-notifier")


def setup_logging(log_dir=None, verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    handlers = [logging.StreamHandler()]

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{date.today().isoformat()}.log")
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


def cmd_explore(config, args):
    """Login and save HTML pages for analysis"""
    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "fixtures"
    )
    with ManageBacClient(config.base_url, config.email, config.password) as client:
        client.login()
        print(f"\nLogin successful! Exploring pages...\n")
        client.explore(output_dir)

        print(f"\nDiscovering children...")
        children = client.get_children()
        if children:
            print(f"\nFound {len(children)} children:")
            for c in children:
                print(f"  - {c.name} (id: {c.managebac_id})")
            print(f"\nUpdate config.yaml with these IDs.")
        else:
            print("Could not auto-detect children. Check saved HTML files manually.")


def _filter_assignments(assignments, config, child_name):
    """Filter out ignored tasks (by config patterns and by ignored.json task IDs)"""
    ignored_ids = load_ignored()

    filtered = []
    for a in assignments:
        # Filter by config ignore_tasks (title substring match)
        if config.ignore_tasks and any(pat in a.title.lower() for pat in config.ignore_tasks):
            continue
        # Filter by ignored.json (task ID match from bot interactions)
        if a.task_id and a.task_id in ignored_ids:
            continue
        filtered.append(a)

    removed = len(assignments) - len(filtered)
    if removed:
        logger.info(f"Filtered out {removed} ignored tasks for {child_name}")
    return filtered


def cmd_run(config, args):
    """Main run: scrape assignments and send notification"""
    with ManageBacClient(config.base_url, config.email, config.password) as client:
        client.login()

        children = client.get_children()

        if not children:
            logger.error("No children found. Run --explore first.")
            sys.exit(1)

        # Fetch assignments for each child
        for child in children:
            assignments = client.get_assignments(child, config.upcoming_days)
            child.assignments = _filter_assignments(assignments, config, child.name)
            overdue = [a for a in child.assignments if a.is_overdue(since=config.overdue_since)]
            upcoming = [a for a in child.assignments if a.is_upcoming(days=config.upcoming_days)]
            logger.info(
                f"{child.name}: {len(overdue)} overdue, {len(upcoming)} upcoming"
            )

    # Save cache for bot_listener to use when building manage keyboard
    save_children_cache(children)

    # Format message
    upcoming_days = config.upcoming_days
    overdue_since = config.overdue_since
    message = format_report(children, upcoming_days=upcoming_days,
                            overdue_since=overdue_since)

    if args.dry_run:
        print("\n--- DRY RUN (Telegram) ---")
        print(message)
        print("\n[Manage Ignore List] button")
        if config.line_enabled:
            plain_message = format_report_plain(children, upcoming_days=upcoming_days,
                                                    overdue_since=overdue_since)
            print("\n--- DRY RUN (LINE) ---")
            print(plain_message)
        print("--- END ---")
        return

    # Send to Telegram with a single "Manage Ignore List" button
    if config.telegram_enabled:
        with TelegramNotifier(config.bot_token, config.chat_id) as notifier:
            notifier.send_message(message, reply_markup=MANAGE_BUTTON)
            logger.info("Telegram notification sent!")

    # Send to LINE group (Flex Message)
    if config.line_enabled:
        with LineNotifier(config.line_channel_token, config.line_group_id) as line:
            line.send_flex_report(children, upcoming_days=upcoming_days,
                                     overdue_since=overdue_since)
            logger.info("LINE notification sent!")


def cmd_test_telegram(config, args):
    """Send a test message to verify Telegram configuration"""
    if not config.telegram_enabled:
        print("Telegram is not configured. Add telegram section to config.yaml.")
        return
    with TelegramNotifier(config.bot_token, config.chat_id) as notifier:
        notifier.send_message(
            "<b>ManageBac Notifier</b>\n\nTest message — configuration is working!",
        )
        print("Test message sent successfully!")


def main():
    parser = argparse.ArgumentParser(description="ManageBac assignment notifier")
    parser.add_argument("--config", help="Config file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("explore", help="Login and explore page structure")
    run_parser = sub.add_parser("run", help="Scrape and send notification")
    run_parser.add_argument("--dry-run", action="store_true", help="Print instead of sending")

    sub.add_parser("test-telegram", help="Send a test Telegram message")

    args = parser.parse_args()
    if not args.command:
        args.command = "run"

    config = Config.load(args.config)
    setup_logging(config.log_dir, args.verbose)

    try:
        if args.command == "explore":
            cmd_explore(config, args)
        elif args.command == "test-telegram":
            cmd_test_telegram(config, args)
        else:
            cmd_run(config, args)
    except LoginError as e:
        logger.error(f"Login failed: {e}")
        _send_error_notification(config, f"Login failed: {e}")
        sys.exit(1)
    except ScrapingError as e:
        logger.error(f"Scraping failed: {e}")
        _send_error_notification(config, f"Scraping error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        _send_error_notification(config, f"Unexpected error: {e}")
        sys.exit(1)


def _send_error_notification(config, error_msg):
    """Try to send error notification via Telegram"""
    if not config.telegram_enabled:
        return
    try:
        with TelegramNotifier(config.bot_token, config.chat_id) as notifier:
            notifier.send_message(
                f"<b>ManageBac Notifier Error</b>\n\n{error_msg}",
            )
    except Exception:
        logger.error("Failed to send error notification to Telegram")


if __name__ == "__main__":
    main()

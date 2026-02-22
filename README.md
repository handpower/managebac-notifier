# ManageBac Notifier

Daily assignment notification tool for [ManageBac](https://www.managebac.com/) parent accounts. Scrapes overdue and upcoming assignments and sends notifications to Telegram and/or LINE.

## Features

- **Multi-child support** — automatically discovers and switches between children
- **Assignment details** — title, subject, tags (Summative/Formative/etc.), due date with time
- **Grouped by subject** — assignments organized by subject for readability
- **Telegram notifications** — HTML formatted report with interactive ignore list via inline buttons
- **LINE notifications** — Flex Message carousel with one card per child
- **Ignore list** — mark tasks as "don't need to submit" via Telegram bot interaction
- **Summative highlight** — Summative tasks marked with pin emoji for visibility
- **Overdue cutoff** — `overdue_since` config to hide last-semester overdue tasks
- **Per-child colors** — customizable LINE Flex Message header colors per child
- **Configurable channels** — Telegram and LINE are both optional

## How It Works

ManageBac does not provide a parent-facing API. This tool logs in via HTTP (httpx + BeautifulSoup4), navigates the parent portal, and parses assignment data from the HTML.

```
ManageBac (web) → scraper.py → models → formatter → Telegram / LINE
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create config

```bash
mkdir -p ~/.config/managebac-notifier
cp config.example.yaml ~/.config/managebac-notifier/config.yaml
chmod 600 ~/.config/managebac-notifier/config.yaml
```

Edit `config.yaml` with your ManageBac credentials and notification settings.

### 3. Explore (first run)

```bash
python managebac_notifier.py explore
```

This logs in, saves HTML pages for analysis, and discovers your children's IDs.

### 4. Test

```bash
# Print report to stdout without sending
python managebac_notifier.py run --dry-run

# Send actual notifications
python managebac_notifier.py run
```

### 5. Schedule (macOS)

```bash
./install.sh
```

This installs two launchd agents:
- **Daily notifier** — runs at 18:00 to scrape and send notifications
- **Bot listener** — persistent daemon that handles Telegram ignore list interactions

## Configuration

```yaml
managebac:
  base_url: "https://YOUR_SCHOOL.managebac.com"
  email: "parent@example.com"
  password: "YOUR_PASSWORD"

children:
  - name: "Child A"
    # id: "12345"  # Discovered by --explore
    # color: "#9B59B6"  # LINE header color (optional)
  - name: "Child B"
    # id: "67890"
    # color: "#0D6EFD"

# Telegram (optional)
telegram:
  bot_token_file: "~/.telegram-bot-token"
  chat_id: "YOUR_CHAT_ID"

# LINE (optional)
line:
  channel_token_file: "~/.line-channel-token"
  group_id: "YOUR_GROUP_ID"

upcoming_days: 3

# Only show overdue tasks with due dates on or after this date
# overdue_since: "2026-01-24"

ignore_tasks:
  # - "some task to always ignore"
```

## Ignore List

The daily Telegram report includes a "Manage Ignore List" button. Tapping it opens an interactive message where you can toggle individual tasks. Ignored tasks won't appear in future reports (both Telegram and LINE).

Ignore state is stored in `~/.config/managebac-notifier/ignored.json`.

## Tech Stack

- **Python 3.12** with httpx, BeautifulSoup4, lxml, PyYAML
- **Telegram Bot API** — direct HTTP calls (no SDK)
- **LINE Messaging API** — Flex Message for rich card layout
- **macOS launchd** — scheduling and daemon management

## Tests

```bash
python -m pytest tests/ -v
```

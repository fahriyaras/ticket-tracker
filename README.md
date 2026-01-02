# Ticket Price Tracker

Simple tool to track ticket prices on VividSeats and StubHub.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Web Interface

```bash
python app.py
```

Open http://localhost:5000 in your browser.

## CLI Usage

### Add an event to track
```bash
# Basic - add event URL
python tracker.py add "https://www.vividseats.com/event/123"

# With quantity filter - only show listings with exactly 2 tickets
python tracker.py add "https://www.stubhub.com/event/456" --quantity 2

# With quantity range - show listings with 2-4 tickets
python tracker.py add "https://www.vividseats.com/event/789" -q 2-4
```

### List tracked events
```bash
python tracker.py list
```

### Track a section for price alerts
```bash
# Alert when Section 101 has tickets at $50 or less
python tracker.py track 1 "Section 101" 50

# Alert when GA Floor has tickets at $75 or less
python tracker.py track 1 "GA Floor" 75
```

### Check prices
```bash
# Check all events
python tracker.py check

# Check specific event
python tracker.py check 1
```

### Stop tracking a section
```bash
python tracker.py untrack 1 "Section 101"
```

### Remove an event
```bash
python tracker.py remove 1
```

## Features

- Scrapes VividSeats and StubHub event pages
- Tracks specific sections with price thresholds
- Quantity filtering (single number or range)
- Only alerts when tickets exist (ignores $0/no-ticket results)
- Simple JSON storage (data.json)

## Notes

- Sites may change their structure - scrapers may need updates
- Run `check` periodically or set up a cron job for monitoring

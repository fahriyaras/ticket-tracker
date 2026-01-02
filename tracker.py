#!/usr/bin/env python3
"""
Simple Ticket Price Tracker for VividSeats and StubHub.

Usage:
    python tracker.py add <url> [--quantity 2] [--quantity 2-3]
    python tracker.py list
    python tracker.py track <event_id> <section> <max_price>
    python tracker.py untrack <event_id> <section>
    python tracker.py check [event_id]
    python tracker.py remove <event_id>
"""

import argparse
import json
import os
import sys
from datetime import datetime
from scrapers import scrape_event, detect_site

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


def load_data():
    """Load tracked events from JSON file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"events": {}}


def save_data(data):
    """Save tracked events to JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def generate_id(data):
    """Generate a simple incremental ID."""
    existing = [int(k) for k in data["events"].keys() if k.isdigit()]
    return str(max(existing, default=0) + 1)


def add_event(url, quantity=None):
    """Add an event to track."""
    site = detect_site(url)
    if not site:
        print("Error: URL must be from VividSeats or StubHub")
        return

    data = load_data()
    event_id = generate_id(data)

    data["events"][event_id] = {
        "url": url,
        "site": site,
        "quantity": quantity,
        "tracked_sections": {},
        "added": datetime.now().isoformat()
    }

    save_data(data)
    print(f"Added event #{event_id}")
    print(f"  URL: {url}")
    print(f"  Site: {site}")
    if quantity:
        print(f"  Quantity filter: {quantity}")

    # Show available sections
    print("\nFetching available sections...")
    try:
        sections = scrape_event(url, quantity)
        if sections:
            print("\nAvailable sections:")
            for section, price in sorted(sections.items(), key=lambda x: x[1]):
                print(f"  {section}: ${price:.2f}")
            print(f"\nUse 'python tracker.py track {event_id} <section> <max_price>' to track a section")
        else:
            print("No tickets found (site may need different scraping approach)")
    except Exception as e:
        print(f"Could not fetch sections: {e}")


def list_events():
    """List all tracked events."""
    data = load_data()

    if not data["events"]:
        print("No events being tracked.")
        return

    for event_id, event in data["events"].items():
        print(f"\n#{event_id} - {event['site'].upper()}")
        print(f"  URL: {event['url']}")
        if event.get("quantity"):
            print(f"  Quantity: {event['quantity']}")

        if event.get("tracked_sections"):
            print("  Tracked sections:")
            for section, max_price in event["tracked_sections"].items():
                print(f"    - {section}: alert if <= ${max_price:.2f}")
        else:
            print("  No sections tracked (use 'track' command)")


def track_section(event_id, section, max_price):
    """Add a section to track with a price threshold."""
    data = load_data()

    if event_id not in data["events"]:
        print(f"Error: Event #{event_id} not found")
        return

    data["events"][event_id]["tracked_sections"][section] = float(max_price)
    save_data(data)

    print(f"Now tracking '{section}' for event #{event_id}")
    print(f"Will alert when price <= ${max_price:.2f}")


def untrack_section(event_id, section):
    """Remove a section from tracking."""
    data = load_data()

    if event_id not in data["events"]:
        print(f"Error: Event #{event_id} not found")
        return

    if section in data["events"][event_id]["tracked_sections"]:
        del data["events"][event_id]["tracked_sections"][section]
        save_data(data)
        print(f"Stopped tracking '{section}' for event #{event_id}")
    else:
        print(f"Section '{section}' was not being tracked")


def check_prices(event_id=None):
    """Check prices and alert on matches."""
    data = load_data()

    if not data["events"]:
        print("No events to check.")
        return

    events_to_check = {}
    if event_id:
        if event_id not in data["events"]:
            print(f"Error: Event #{event_id} not found")
            return
        events_to_check[event_id] = data["events"][event_id]
    else:
        events_to_check = data["events"]

    alerts = []

    for eid, event in events_to_check.items():
        print(f"\nChecking event #{eid}...")

        try:
            sections = scrape_event(event["url"], event.get("quantity"))

            if not sections:
                print("  No tickets available")
                continue

            print(f"  Found {len(sections)} sections with tickets")

            # Check tracked sections for alerts
            for tracked_section, max_price in event.get("tracked_sections", {}).items():
                # Find matching sections (case-insensitive partial match)
                for section, price in sections.items():
                    if tracked_section.lower() in section.lower():
                        if price > 0 and price <= max_price:
                            alerts.append({
                                "event_id": eid,
                                "section": section,
                                "price": price,
                                "threshold": max_price,
                                "url": event["url"]
                            })

            # Show all current prices
            print("  Current prices:")
            for section, price in sorted(sections.items(), key=lambda x: x[1]):
                marker = ""
                for ts, mp in event.get("tracked_sections", {}).items():
                    if ts.lower() in section.lower():
                        if price <= mp:
                            marker = " *** ALERT ***"
                        else:
                            marker = f" (tracking <= ${mp:.2f})"
                print(f"    {section}: ${price:.2f}{marker}")

        except Exception as e:
            print(f"  Error: {e}")

    # Summary of alerts
    if alerts:
        print("\n" + "=" * 50)
        print("🎫 PRICE ALERTS!")
        print("=" * 50)
        for alert in alerts:
            print(f"\nEvent #{alert['event_id']}: {alert['section']}")
            print(f"  Price: ${alert['price']:.2f} (threshold: ${alert['threshold']:.2f})")
            print(f"  URL: {alert['url']}")
    else:
        print("\nNo alerts - no tracked sections at or below threshold.")


def remove_event(event_id):
    """Remove an event from tracking."""
    data = load_data()

    if event_id not in data["events"]:
        print(f"Error: Event #{event_id} not found")
        return

    del data["events"][event_id]
    save_data(data)
    print(f"Removed event #{event_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Track ticket prices on VividSeats and StubHub"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Add event
    add_parser = subparsers.add_parser("add", help="Add an event to track")
    add_parser.add_argument("url", help="Event URL (VividSeats or StubHub)")
    add_parser.add_argument(
        "--quantity", "-q",
        help="Ticket quantity filter (e.g., '2' or '2-3')"
    )

    # List events
    subparsers.add_parser("list", help="List all tracked events")

    # Track section
    track_parser = subparsers.add_parser("track", help="Track a section with price alert")
    track_parser.add_argument("event_id", help="Event ID (from 'list' command)")
    track_parser.add_argument("section", help="Section name to track")
    track_parser.add_argument("max_price", type=float, help="Alert when price <= this")

    # Untrack section
    untrack_parser = subparsers.add_parser("untrack", help="Stop tracking a section")
    untrack_parser.add_argument("event_id", help="Event ID")
    untrack_parser.add_argument("section", help="Section name to untrack")

    # Check prices
    check_parser = subparsers.add_parser("check", help="Check current prices")
    check_parser.add_argument("event_id", nargs="?", help="Event ID (optional, checks all if omitted)")

    # Remove event
    remove_parser = subparsers.add_parser("remove", help="Remove an event")
    remove_parser.add_argument("event_id", help="Event ID to remove")

    args = parser.parse_args()

    if args.command == "add":
        add_event(args.url, args.quantity)
    elif args.command == "list":
        list_events()
    elif args.command == "track":
        track_section(args.event_id, args.section, args.max_price)
    elif args.command == "untrack":
        untrack_section(args.event_id, args.section)
    elif args.command == "check":
        check_prices(args.event_id)
    elif args.command == "remove":
        remove_event(args.event_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

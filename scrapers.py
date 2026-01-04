"""
Simple scrapers for VividSeats and StubHub ticket prices.
"""

import re
import json
from playwright.sync_api import sync_playwright


def parse_quantity_filter(quantity_str):
    """
    Parse quantity filter string into min/max values.
    Examples: "2" -> (2, 2), "2-3" -> (2, 3), None -> (None, None)
    """
    if not quantity_str:
        return None, None

    quantity_str = str(quantity_str).strip()
    if "-" in quantity_str:
        parts = quantity_str.split("-")
        return int(parts[0]), int(parts[1])
    else:
        qty = int(quantity_str)
        return qty, qty


def matches_quantity(ticket_qty, min_qty, max_qty):
    """Check if ticket quantity matches the filter."""
    if min_qty is None:
        return True
    return min_qty <= ticket_qty <= max_qty


def detect_site(url):
    """Detect which site the URL is from."""
    if "vividseats.com" in url:
        return "vividseats"
    elif "stubhub.com" in url:
        return "stubhub"
    else:
        return None


def scrape_vividseats(url, quantity_filter=None):
    """
    Scrape VividSeats for section prices.
    Returns dict: {section_name: lowest_price}
    """
    min_qty, max_qty = parse_quantity_filter(quantity_filter)
    sections = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

        try:
            page.goto(url, timeout=30000)
            page.wait_for_timeout(5000)

            # Look for ticket data in script tags
            scripts = page.query_selector_all("script")
            for script in scripts:
                try:
                    text = script.inner_text()
                    # Look for JSON with ticket/listing data
                    if '"tickets"' in text or '"listings"' in text or '"ticketGroups"' in text:
                        # Try to find and parse embedded JSON
                        json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
                        for match in json_matches:
                            try:
                                data = json.loads(match)
                                tickets = data.get("tickets", data.get("listings", data.get("ticketGroups", [])))
                                if isinstance(tickets, list):
                                    for ticket in tickets:
                                        section = ticket.get("section", ticket.get("s", "Unknown"))
                                        price = ticket.get("price", ticket.get("p", 0))
                                        qty = ticket.get("quantity", ticket.get("q", 1))
                                        if isinstance(price, dict):
                                            price = price.get("amount", 0)
                                        if price and float(price) > 0:
                                            price = float(price)
                                            if matches_quantity(qty, min_qty, max_qty):
                                                if section not in sections or price < sections[section]:
                                                    sections[section] = price
                            except (json.JSONDecodeError, TypeError):
                                continue
                except Exception:
                    continue

        except Exception as e:
            print(f"Error scraping VividSeats: {e}")
        finally:
            browser.close()

    return sections


def scrape_stubhub(url, quantity_filter=None):
    """
    Scrape StubHub for section prices.
    Returns dict: {section_name: lowest_price}
    """
    min_qty, max_qty = parse_quantity_filter(quantity_filter)
    sections = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

        try:
            page.goto(url, timeout=30000)
            page.wait_for_timeout(5000)

            # Method 1: Look for __NEXT_DATA__ (Next.js apps)
            next_data_el = page.query_selector("script#__NEXT_DATA__")
            if next_data_el:
                try:
                    data = json.loads(next_data_el.inner_text())
                    # Try various paths where listings might be
                    props = data.get("props", {}).get("pageProps", {})

                    # Check common paths
                    listings = props.get("listings", [])
                    if not listings:
                        listings = props.get("initialListings", [])
                    if not listings:
                        listings = props.get("eventListings", {}).get("listings", [])
                    if not listings and "event" in props:
                        listings = props.get("event", {}).get("listings", [])

                    for listing in listings:
                        section = listing.get("section", listing.get("sectionName", listing.get("s", "Unknown")))
                        row = listing.get("row", listing.get("r", ""))

                        # Get price - might be nested
                        price = listing.get("price", 0)
                        if isinstance(price, dict):
                            price = price.get("amount", price.get("value", 0))
                        if not price:
                            price = listing.get("pricePerTicket", {}).get("amount", 0)
                        if not price:
                            price = listing.get("currentPrice", {}).get("amount", 0)

                        qty = listing.get("quantity", listing.get("availableTickets", listing.get("q", 1)))

                        if price and float(price) > 0:
                            price = float(price)
                            if matches_quantity(qty, min_qty, max_qty):
                                section_key = f"{section}" if not row else f"{section} Row {row}"
                                if section_key not in sections or price < sections[section_key]:
                                    sections[section_key] = price
                except (json.JSONDecodeError, TypeError, KeyError) as e:
                    print(f"Error parsing __NEXT_DATA__: {e}")

            # Method 2: Look for inline script data
            if not sections:
                scripts = page.query_selector_all("script")
                for script in scripts:
                    try:
                        text = script.inner_text()
                        if "listing" in text.lower() and "price" in text.lower():
                            # Try to extract JSON arrays/objects
                            json_matches = re.findall(r'\[[\s\S]*?\]|\{[\s\S]*?\}', text)
                            for match in json_matches:
                                try:
                                    data = json.loads(match)
                                    items = data if isinstance(data, list) else [data]
                                    for item in items:
                                        if isinstance(item, dict) and ("section" in item or "price" in item):
                                            section = item.get("section", item.get("sectionName", "Unknown"))
                                            price = item.get("price", 0)
                                            if isinstance(price, dict):
                                                price = price.get("amount", 0)
                                            qty = item.get("quantity", 1)
                                            if price and float(price) > 0:
                                                price = float(price)
                                                if matches_quantity(qty, min_qty, max_qty):
                                                    if section not in sections or price < sections[section]:
                                                        sections[section] = price
                                except (json.JSONDecodeError, TypeError):
                                    continue
                    except Exception:
                        continue

            # Method 3: Parse visible DOM elements
            if not sections:
                # Wait a bit more for dynamic content
                page.wait_for_timeout(2000)

                # Try various selectors StubHub might use
                selectors = [
                    "[data-testid='listing']",
                    "[class*='ListingCard']",
                    "[class*='listing-card']",
                    "[class*='TicketCard']",
                    "div[class*='Listing']"
                ]

                for selector in selectors:
                    cards = page.query_selector_all(selector)
                    if cards:
                        for card in cards:
                            try:
                                text = card.inner_text()
                                lines = [l.strip() for l in text.split('\n') if l.strip()]

                                section = None
                                price = None

                                for line in lines:
                                    # Look for section info
                                    if re.match(r'^(Section|Sec\.?)\s+', line, re.I):
                                        section = line
                                    elif re.match(r'^[A-Z].*\d', line) and not price:
                                        section = line

                                    # Look for price
                                    price_match = re.search(r'\$[\d,]+(?:\.\d{2})?', line)
                                    if price_match:
                                        price = float(re.sub(r'[^\d.]', '', price_match.group()))

                                if section and price and price > 0:
                                    if section not in sections or price < sections[section]:
                                        sections[section] = price
                            except Exception:
                                continue
                        break

        except Exception as e:
            print(f"Error scraping StubHub: {e}")
        finally:
            browser.close()

    return sections


def scrape_event(url, quantity_filter=None):
    """
    Scrape an event URL and return section prices.
    Automatically detects the site.
    """
    site = detect_site(url)

    if site == "vividseats":
        return scrape_vividseats(url, quantity_filter)
    elif site == "stubhub":
        return scrape_stubhub(url, quantity_filter)
    else:
        raise ValueError("Unsupported site. URL must be from VividSeats or StubHub.")

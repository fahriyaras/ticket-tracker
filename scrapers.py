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

    quantity_str = quantity_str.strip()
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

        try:
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)  # Wait for dynamic content

            # Try to find ticket listings - VividSeats uses various selectors
            # Look for the ticket data in the page
            content = page.content()

            # VividSeats embeds ticket data in script tags as JSON
            scripts = page.query_selector_all("script")
            for script in scripts:
                text = script.inner_text()
                if "ticketGroups" in text or "listings" in text:
                    # Try to extract JSON data
                    try:
                        # Find JSON objects in the script
                        matches = re.findall(r'\{[^{}]*"ticketGroups"[^{}]*\}|\{[^{}]*"listings"[^{}]*\}', text)
                        for match in matches:
                            data = json.loads(match)
                            # Process ticket data
                            for ticket in data.get("ticketGroups", data.get("listings", [])):
                                section = ticket.get("section", ticket.get("sectionName", "Unknown"))
                                price = ticket.get("price", ticket.get("listingPrice", 0))
                                qty = ticket.get("quantity", ticket.get("availableQuantity", 1))

                                if price and price > 0:
                                    if matches_quantity(qty, min_qty, max_qty):
                                        if section not in sections or price < sections[section]:
                                            sections[section] = price
                    except (json.JSONDecodeError, KeyError):
                        continue

            # Fallback: Try to scrape visible ticket elements
            if not sections:
                ticket_rows = page.query_selector_all("[data-testid='ticket-row'], .ticket-row, .listing-row")
                for row in ticket_rows:
                    try:
                        section_el = row.query_selector("[data-testid='section'], .section, .ticket-section")
                        price_el = row.query_selector("[data-testid='price'], .price, .ticket-price")
                        qty_el = row.query_selector("[data-testid='quantity'], .quantity, .ticket-quantity")

                        if section_el and price_el:
                            section = section_el.inner_text().strip()
                            price_text = price_el.inner_text().strip()
                            price = float(re.sub(r'[^\d.]', '', price_text)) if price_text else 0

                            qty = 1
                            if qty_el:
                                qty_text = qty_el.inner_text()
                                qty_match = re.search(r'\d+', qty_text)
                                if qty_match:
                                    qty = int(qty_match.group())

                            if price > 0 and matches_quantity(qty, min_qty, max_qty):
                                if section not in sections or price < sections[section]:
                                    sections[section] = price
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

        try:
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)  # Wait for dynamic content

            # StubHub also uses embedded JSON data
            content = page.content()

            # Look for __NEXT_DATA__ or similar embedded data
            next_data = page.query_selector("script#__NEXT_DATA__")
            if next_data:
                try:
                    data = json.loads(next_data.inner_text())
                    # Navigate to ticket listings in the data structure
                    listings = (
                        data.get("props", {})
                        .get("pageProps", {})
                        .get("listings", [])
                    )
                    for listing in listings:
                        section = listing.get("section", listing.get("sectionName", "Unknown"))
                        price = listing.get("price", listing.get("currentPrice", {}).get("amount", 0))
                        qty = listing.get("quantity", listing.get("availableTickets", 1))

                        if price and price > 0:
                            if matches_quantity(qty, min_qty, max_qty):
                                if section not in sections or price < sections[section]:
                                    sections[section] = price
                except (json.JSONDecodeError, KeyError):
                    pass

            # Fallback: scrape visible elements
            if not sections:
                ticket_cards = page.query_selector_all("[data-testid='listing-card'], .listing-card, .ticket-card")
                for card in ticket_cards:
                    try:
                        section_el = card.query_selector("[data-testid='section-name'], .section-name, .section")
                        price_el = card.query_selector("[data-testid='price'], .price, .listing-price")
                        qty_el = card.query_selector("[data-testid='quantity'], .quantity")

                        if section_el and price_el:
                            section = section_el.inner_text().strip()
                            price_text = price_el.inner_text().strip()
                            price = float(re.sub(r'[^\d.]', '', price_text)) if price_text else 0

                            qty = 1
                            if qty_el:
                                qty_text = qty_el.inner_text()
                                qty_match = re.search(r'\d+', qty_text)
                                if qty_match:
                                    qty = int(qty_match.group())

                            if price > 0 and matches_quantity(qty, min_qty, max_qty):
                                if section not in sections or price < sections[section]:
                                    sections[section] = price
                    except Exception:
                        continue

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
        raise ValueError(f"Unsupported site. URL must be from VividSeats or StubHub.")

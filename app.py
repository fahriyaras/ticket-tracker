#!/usr/bin/env python3
"""
Simple web interface for Ticket Price Tracker.
Run with: python app.py
"""

import json
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from scrapers import scrape_event, detect_site

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"events": {}}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def generate_id(data):
    existing = [int(k) for k in data["events"].keys() if k.isdigit()]
    return str(max(existing, default=0) + 1)


@app.route("/")
def index():
    data = load_data()
    return render_template("index.html", events=data["events"])


@app.route("/add", methods=["POST"])
def add_event():
    url = request.form.get("url", "").strip()
    quantity = request.form.get("quantity", "").strip() or None

    site = detect_site(url)
    if not site:
        return jsonify({"error": "URL must be from VividSeats or StubHub"}), 400

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

    return redirect(url_for("index"))


@app.route("/remove/<event_id>", methods=["POST"])
def remove_event(event_id):
    data = load_data()
    if event_id in data["events"]:
        del data["events"][event_id]
        save_data(data)
    return redirect(url_for("index"))


@app.route("/track/<event_id>", methods=["POST"])
def track_section(event_id):
    section = request.form.get("section", "").strip()
    max_price = request.form.get("max_price", "").strip()

    if not section or not max_price:
        return jsonify({"error": "Section and max price required"}), 400

    data = load_data()
    if event_id not in data["events"]:
        return jsonify({"error": "Event not found"}), 404

    data["events"][event_id]["tracked_sections"][section] = float(max_price)
    save_data(data)

    return redirect(url_for("index"))


@app.route("/untrack/<event_id>/<section>", methods=["POST"])
def untrack_section(event_id, section):
    data = load_data()
    if event_id in data["events"]:
        data["events"][event_id]["tracked_sections"].pop(section, None)
        save_data(data)
    return redirect(url_for("index"))


@app.route("/scrape/<event_id>")
def scrape(event_id):
    data = load_data()
    if event_id not in data["events"]:
        return jsonify({"error": "Event not found"}), 404

    event = data["events"][event_id]
    try:
        sections = scrape_event(event["url"], event.get("quantity"))

        # Check for alerts
        alerts = []
        for tracked, max_price in event.get("tracked_sections", {}).items():
            for section, price in sections.items():
                if tracked.lower() in section.lower() and 0 < price <= max_price:
                    alerts.append({
                        "section": section,
                        "price": price,
                        "threshold": max_price
                    })

        return jsonify({
            "sections": sections,
            "alerts": alerts
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/check")
def check_all():
    """Check all events and return results."""
    data = load_data()
    results = {}

    for event_id, event in data["events"].items():
        try:
            sections = scrape_event(event["url"], event.get("quantity"))
            alerts = []
            for tracked, max_price in event.get("tracked_sections", {}).items():
                for section, price in sections.items():
                    if tracked.lower() in section.lower() and 0 < price <= max_price:
                        alerts.append({
                            "section": section,
                            "price": price,
                            "threshold": max_price
                        })
            results[event_id] = {"sections": sections, "alerts": alerts, "error": None}
        except Exception as e:
            results[event_id] = {"sections": {}, "alerts": [], "error": str(e)}

    return jsonify(results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

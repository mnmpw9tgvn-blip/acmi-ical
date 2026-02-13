import hashlib
from datetime import timedelta
from urllib.parse import urljoin

import requests
from dateutil import parser
from icalendar import Calendar, Event

API_ROOT = "https://admin.acmi.net.au"
API_URL = "https://admin.acmi.net.au/api/v2/calendar/?format=json&limit=200"
ACMI_SITE = "https://www.acmi.net.au"

# Film = 1, Film + Talk = 61 (from /api/v2/calendar/filters/)
FILM_EVENT_TYPE_IDS = {1, 61}

DEFAULT_DURATION_HOURS = 2


def stable_uid(item: dict) -> str:
    ev = item.get("event") or {}
    raw = f'{item.get("id")}::{ev.get("id")}::{item.get("start_datetime")}::{item.get("end_datetime")}'
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return f"{h}@acmi-ical"


def is_film(item: dict) -> bool:
    ev = item.get("event") or {}
    et = ev.get("event_type") or {}
    return et.get("id") in FILM_EVENT_TYPE_IDS


def get_film_year(ev: dict):
    """
    Try common year fields ACMI might provide.
    Returns an int year or None.
    """
    for key in ("year", "release_year", "production_year"):
        y = ev.get(key)
        if isinstance(y, int) and 1800 <= y <= 2100:
            return y
        if isinstance(y, str) and y.isdigit():
            yi = int(y)
            if 1800 <= yi <= 2100:
                return yi
    return None


def fetch_all_items() -> list:
    """
    Follows pagination (the API often returns a 'next' URL).
    """
    url = API_URL
    all_items = []

    while url:
        data = requests.get(url, timeout=60).json()
        all_items.extend(data.get("items", []))
        url = data.get("next")

        # Some APIs return relative next URLs; make them absolute if needed
        if url and url.startswith("/"):
            url = urljoin(API_ROOT, url)

    return all_items


def main():
    items = fetch_all_items()

    cal = Calendar()
    cal.add("prodid", "-//ACMI Films//acmi-ical//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "ACMI Films")
    cal.add("x-wr-timezone", "Australia/Melbourne")

    kept = 0

    for item in items:
        if not is_film(item):
            continue

        ev = item.get("event") or {}
        base_title = ev.get("title") or "ACMI Film"
        year = get_film_year(ev)
        title = f"{base_title} ({year})" if year else base_title

        start = parser.isoparse(item["start_datetime"])

        end_raw = item.get("end_datetime")
        if end_raw:
            end = parser.isoparse(end_raw)
        else:
            end = start + timedelta(hours=DEFAULT_DURATION_HOURS)

        venue = item.get("venue") or "ACMI, Fed Square"

        url_path = ev.get("url") or "/"
        event_url = urljoin(ACMI_SITE, url_path.lstrip("/"))

        purchase_url = item.get("purchase_url") or ""
        desc = event_url + (f"\n\nTickets: {purchase_url}" if purchase_url else "")

        ical_event = Event()
        ical_event.add("uid", stable_uid(item))
        ical_event.add("summary", title)
        ical_event.add("dtstart", start)
        ical_event.add("dtend", end)
        ical_event.add("location", venue)
        ical_event.add("url", event_url)
        ical_event.add("description", desc)

        cal.add_component(ical_event)
        kept += 1

    with open("acmi.ics", "wb") as f:
        f.write(cal.to_ical())

    print(f"Saved acmi.ics with {kept} film events.")


if __name__ == "__main__":
    main()

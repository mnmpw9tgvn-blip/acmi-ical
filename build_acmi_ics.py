import hashlib
from datetime import timedelta, datetime
from urllib.parse import urljoin

import requests
from dateutil import parser
from icalendar import Calendar, Event

API_URL = "https://admin.acmi.net.au/api/v2/calendar/?format=json&limit=500"
ACMI_SITE = "https://www.acmi.net.au"

# Film = 1, Film + Talk = 61
FILM_EVENT_TYPE_IDS = {1, 61}


def stable_uid(item):
    ev = item.get("event") or {}
    raw = f'{item.get("id")}::{ev.get("id")}::{item.get("start_datetime")}::{item.get("end_datetime")}'
    return hashlib.sha1(raw.encode("utf-8")).hexdigest() + "@acmi-ical"


def is_film(item):
    ev = item.get("event") or {}
    et = ev.get("event_type") or {}
    return et.get("id") in FILM_EVENT_TYPE_IDS


def main():
    data = requests.get(API_URL, timeout=60).json()
    items = data.get("items", [])

    cal = Calendar()
    cal.add("prodid", "-//ACMI Films//acmi-ical//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "ACMI Films")
    cal.add("x-wr-timezone", "Australia/Melbourne")

    kept = 0

    for item in items:
        if not is_film(item):
            continue

        start = parser.isoparse(item["start_datetime"])

        # skip past screenings
        if start < datetime.now(start.tzinfo):
            continue

        end_raw = item.get("end_datetime")
        if end_raw:
            end = parser.isoparse(end_raw)
        else:
            end = start + timedelta(hours=2)

        ev = item.get("event") or {}
        title = ev.get("title") or "ACMI Film"

        venue = item.get("venue") or "ACMI, Fed Square"

        url_path = ev.get("url") or "/"
        event_url = urljoin(ACMI_SITE, url_path.lstrip("/"))

        purchase_url = item.get("purchase_url") or ""
        desc = event_url
        if purchase_url:
            desc += f"\nTickets: {purchase_url}"

        e = Event()
        e.add("uid", stable_uid(item))
        e.add("summary", title)
        e.add("dtstart", start)
        e.add("dtend", end)
        e.add("location", venue)
        e.add("url", event_url)
        e.add("description", desc)

        cal.add_component(e)
        kept += 1

    with open("acmi.ics", "wb") as f:
        f.write(cal.to_ical())

    print(f"Saved acmi.ics with {kept} film events.")


if __name__ == "__main__":
    main()

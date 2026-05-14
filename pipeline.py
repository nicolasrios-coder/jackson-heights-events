#!/usr/bin/env python3
"""
Event Pipeline: Jackson Heights Insider
  Step 1 – Pull   : fetch HTML from events listing pages
  Step 2 – Clean  : parse into structured Event dataclasses
  Step 3 – Output : filter for tomorrow and print / save JSON
"""

import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

BASE_URL = "https://jacksonheightsinsider.com/events"


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Event:
    title: str
    url: str
    start_date: Optional[date]
    start_time: Optional[str]
    end_time: Optional[str]
    venue: Optional[str]
    address: Optional[str]
    description: Optional[str]
    price: Optional[str]
    raw_date: Optional[str]


# ── Step 1: Pull ──────────────────────────────────────────────────────────────

def fetch_pages() -> list[str]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; EventPipeline/1.0)"}
    print(f"  GET {BASE_URL}")
    resp = requests.get(BASE_URL, headers=headers, timeout=15)
    resp.raise_for_status()
    return [resp.text]


# ── Step 2: Clean ─────────────────────────────────────────────────────────────

def _parse_date(text: str) -> Optional[date]:
    """'May 13 @ 7:00 pm' or 'May 13' → date(2026, 5, 13)"""
    if not text:
        return None
    date_part = re.split(r"\s*@\s*", text.strip(), maxsplit=1)[0].strip()
    today = date.today()
    for year in (today.year, today.year + 1):
        try:
            candidate = dateparser.parse(
                f"{date_part} {year}", default=datetime(year, 1, 1)
            ).date()
            if candidate >= today:
                return candidate
        except (ValueError, OverflowError):
            pass
    return None


def _parse_time(text: str) -> Optional[str]:
    """Strip and return a bare time string, or None if empty."""
    t = text.strip() if text else ""
    return t or None


def _text(el) -> Optional[str]:
    return el.get_text(" ", strip=True) if el else None


def parse_events(html: str) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")

    articles = soup.find_all("article", class_=lambda c: c and "tribe_events" in c)
    if not articles:
        articles = soup.find_all(attrs={"class": re.compile(r"tribe.event")})

    events = []
    for art in articles:
        # Title + URL
        title_el = art.find(class_="tribe-events-calendar-list__event-title")
        link = art.find(class_="tribe-events-calendar-list__event-title-link") or \
               (title_el or art).find("a", href=True)
        title = _text(title_el) or "Untitled"
        url = link["href"] if link else ""

        # Date — "May 13 @ 7:00 pm"
        date_start_el = art.find(class_="tribe-event-date-start")
        raw_date = _text(date_start_el) or ""
        start_date = _parse_date(raw_date)

        # Start time (after @), end time from tribe-event-time
        start_time = end_time = None
        if "@" in raw_date:
            start_time = _parse_time(raw_date.split("@", 1)[1])
        time_end_el = art.find(class_="tribe-event-time")
        if time_end_el:
            end_time = _parse_time(_text(time_end_el))

        # Venue — title field contains "Name, full address"
        venue = address = None
        venue_title_el = art.find(class_="tribe-events-calendar-list__event-venue-title")
        if venue_title_el:
            full = _text(venue_title_el) or ""
            parts = full.split(",", 1)
            venue = parts[0].strip()
            address = parts[1].strip() if len(parts) > 1 else None

        # Description
        desc_el = art.find(class_="tribe-events-calendar-list__event-description")
        description = _text(desc_el)

        # Price
        price_el = art.find(class_=re.compile(r"tribe-ticket-cost|tribe-cost"))
        price = _text(price_el)

        events.append(Event(
            title=title,
            url=url,
            start_date=start_date,
            start_time=start_time,
            end_time=end_time,
            venue=venue,
            address=address,
            description=description,
            price=price,
            raw_date=raw_date,
        ))

    return events


# ── Step 3: Output ────────────────────────────────────────────────────────────

def filter_tomorrow(events: list[Event]) -> list[Event]:
    tomorrow = date.today() + timedelta(days=1)
    return [e for e in events if e.start_date == tomorrow]


def _format_event(event: Event, index: int) -> str:
    lines = [f"{index}. {event.title}"]
    if event.start_time:
        t = f"{event.start_time} – {event.end_time}" if event.end_time else event.start_time
        lines.append(f"   Time:    {t}")
    if event.venue:
        lines.append(f"   Venue:   {event.venue}")
    if event.address:
        lines.append(f"   Address: {event.address}")
    if event.price:
        lines.append(f"   Price:   {event.price}")
    if event.description:
        snippet = event.description[:160].rstrip()
        if len(event.description) > 160:
            snippet += "…"
        lines.append(f"   About:   {snippet}")
    if event.url:
        lines.append(f"   URL:     {event.url}")
    return "\n".join(lines)


def print_events(events: list[Event]) -> None:
    tomorrow = date.today() + timedelta(days=1)
    label = tomorrow.strftime("%A, %B %d, %Y").replace(" 0", " ")
    print(f"\n{'=' * 60}")
    print(f"  Events for {label}")
    print(f"{'=' * 60}")
    if not events:
        print("  No events found for tomorrow.\n")
        return
    print(f"  {len(events)} event(s) found\n")
    for i, ev in enumerate(events, 1):
        print(_format_event(ev, i))
        print()


def save_json(events: list[Event], path: str) -> None:
    records = [
        {
            "title": e.title,
            "url": e.url,
            "date": e.start_date.isoformat() if e.start_date else None,
            "start_time": e.start_time,
            "end_time": e.end_time,
            "venue": e.venue,
            "address": e.address,
            "description": e.description,
            "price": e.price,
        }
        for e in events
    ]
    with open(path, "w") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
    print(f"  Saved → {path}")


# ── Community filter ──────────────────────────────────────────────────────────

_COMMUNITY_KEYWORDS = {
    # immigrant / migrant terms
    "immigrant", "immigrants", "inmigrante", "inmigrantes", "migrante", "migrantes",
    "undocumented", "indocumentado", "indocumentados", "asylum", "asilo",
    # language / culture
    "spanish", "español", "española", "bilingual", "bilingüe",
    "latin", "latino", "latina", "latinx", "latinoamerica", "latinoamérica",
    "hispano", "hispana", "hispanic",
    # latin american countries (English + Spanish names)
    "mexico", "méxico", "mexicano", "mexicana",
    "guatemala", "guatemalteco", "guatemalteca",
    "honduras", "hondureño", "hondureña",
    "el salvador", "salvadoreño", "salvadoreña",
    "nicaragua", "nicaragüense",
    "costa rica", "costarricense",
    "panama", "panamá", "panameño", "panameña",
    "cuba", "cubano", "cubana",
    "dominican", "dominicano", "dominicana", "república dominicana",
    "puerto rico", "puertorriqueño", "puertorriqueña",
    "colombia", "colombiano", "colombiana",
    "venezuela", "venezolano", "venezolana",
    "ecuador", "ecuatoriano", "ecuatoriana",
    "peru", "perú", "peruano", "peruana",
    "bolivia", "boliviano", "boliviana",
    "chile", "chileno", "chilena",
    "argentina", "argentino", "argentina",
    "uruguay", "uruguayo", "uruguaya",
    "paraguay", "paraguayo", "paraguaya",
    "brazil", "brasil", "brasileño", "brasileña",
    "haiti", "haití", "haitiano", "haitiana", "kreyòl", "kreyol",
    # Spanish-language signal characters / common words in event text
    "folklórico", "folklorico", "tejido", "zumba", "cumbia", "salsa", "merengue",
    "bachata", "reggaeton", "reggaetón", "bomba", "plena", "vallenato",
    "mariachi", "tango", "flamenco", "bailable",
    "comunidad", "vecinos", "familia", "gratis", "gratuito",
    "clases", "clase", "talleres", "taller",
}

# Spanish-specific characters that strongly signal Spanish text
_SPANISH_CHARS = re.compile(r"[áéíóúüñÁÉÍÓÚÜÑ¿¡]")


def is_community_relevant(event: Event) -> bool:
    haystack = " ".join(filter(None, [
        event.title, event.description, event.venue, event.address,
    ])).lower()
    if _SPANISH_CHARS.search(haystack):
        return True
    return any(kw in haystack for kw in _COMMUNITY_KEYWORDS)


# ── Text output ───────────────────────────────────────────────────────────────

def _event_block(ev: Event, highlight: bool = False) -> list[str]:
    prefix = ">>> " if highlight else "    "
    lines = [f"{prefix}{ev.title}"]
    if ev.start_time:
        t = f"{ev.start_time} – {ev.end_time}" if ev.end_time else ev.start_time
        lines.append(f"    Time:    {t}")
    if ev.start_date:
        lines.append(f"    Date:    {ev.start_date.strftime('%B %d, %Y')}")
    if ev.venue:
        venue_line = ev.venue
        if ev.address:
            venue_line += f", {ev.address}"
        lines.append(f"    Venue:   {venue_line}")
    if ev.price:
        lines.append(f"    Price:   {ev.price}")
    if ev.description:
        lines.append(f"    About:   {ev.description}")
    if ev.url:
        lines.append(f"    Link:    {ev.url}")
    lines.append("")
    return lines


def save_text(events: list[Event], path: str) -> None:
    from itertools import groupby

    today = date.today()
    featured = [e for e in events if is_community_relevant(e)]
    rest = [e for e in events if not is_community_relevant(e)]

    lines = [
        "Jackson Heights Insider — All Events",
        f"Generated: {today.strftime('%A, %B %d, %Y')}",
        f"Source: {BASE_URL}",
        "=" * 60,
        "",
    ]

    # ── Featured section ──
    if featured:
        lines += [
            f"★ COMMUNITY SPOTLIGHT ({len(featured)} events) ★",
            "  Spanish-language, immigrant & Latin American community events",
            "  (marked with >>>)",
            "",
        ]
        sorted_featured = sorted(featured, key=lambda e: (e.start_date or date.max, e.start_time or ""))
        for event_date, group in groupby(sorted_featured, key=lambda e: e.start_date):
            label = event_date.strftime("%A, %B %d, %Y").replace(" 0", " ") if event_date else "Date unknown"
            lines += [f"── {label} ──", ""]
            for ev in group:
                lines.extend(_event_block(ev, highlight=True))
        lines += ["=" * 60, ""]

    # ── All events by date ──
    lines += ["ALL EVENTS", ""]
    sorted_all = sorted(events, key=lambda e: (e.start_date or date.max, e.start_time or ""))
    for event_date, group in groupby(sorted_all, key=lambda e: e.start_date):
        label = event_date.strftime("%A, %B %d, %Y").replace(" 0", " ") if event_date else "Date unknown"
        lines += [f"── {label} ──", ""]
        for ev in group:
            lines.extend(_event_block(ev, highlight=is_community_relevant(ev)))

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"  Saved → {path}")
    print(f"  {len(featured)} community-relevant event(s) highlighted")


def save_html(events: list[Event], path: str) -> None:
    from itertools import groupby
    import os

    today = date.today()
    featured = [e for e in events if is_community_relevant(e)]

    def event_card(ev: Event, spotlight: bool = False) -> str:
        card_class = "card spotlight" if spotlight else "card"
        time_str = ""
        if ev.start_time:
            time_str = f"{ev.start_time} – {ev.end_time}" if ev.end_time else ev.start_time
        venue_str = ev.venue or ""
        if venue_str and ev.address:
            venue_str += f", {ev.address}"
        desc_str = f'<p class="desc">{ev.description}</p>' if ev.description else ""
        price_str = f'<span class="price">{ev.price}</span>' if ev.price else ""
        badge = '<span class="badge">★ Community</span>' if spotlight else ""
        title_html = f'<a href="{ev.url}" target="_blank">{ev.title}</a>' if ev.url else ev.title
        return f"""
        <div class="{card_class}">
          <div class="card-header">
            {badge}
            <h3>{title_html}</h3>
          </div>
          <div class="meta">
            {f'<span>🕐 {time_str}</span>' if time_str else ''}
            {f'<span>📍 {venue_str}</span>' if venue_str else ''}
            {price_str}
          </div>
          {desc_str}
        </div>"""

    sorted_all = sorted(events, key=lambda e: (e.start_date or date.max, e.start_time or ""))

    day_sections = []
    for event_date, group in groupby(sorted_all, key=lambda e: e.start_date):
        label = event_date.strftime("%A, %B %d, %Y").replace(" 0", " ") if event_date else "Date unknown"
        cards = "".join(event_card(ev, spotlight=is_community_relevant(ev)) for ev in group)
        day_sections.append(f'<section><h2 class="day-heading">{label}</h2>{cards}</section>')

    spotlight_cards = "".join(
        event_card(ev, spotlight=True)
        for ev in sorted(featured, key=lambda e: (e.start_date or date.max, e.start_time or ""))
    )
    spotlight_section = f"""
    <div class="spotlight-block">
      <h2>★ Community Spotlight — {len(featured)} events</h2>
      <p class="subtitle">Spanish-language, immigrant &amp; Latin American community events</p>
      {spotlight_cards}
    </div>""" if featured else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Jackson Heights Events</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #f5f5f5; color: #1a1a1a; line-height: 1.5; }}
    header {{ background: #1a1a2e; color: white; padding: 1.5rem 2rem; }}
    header h1 {{ font-size: 1.4rem; font-weight: 700; }}
    header p  {{ font-size: 0.85rem; opacity: 0.7; margin-top: 0.25rem; }}
    main {{ max-width: 800px; margin: 0 auto; padding: 1.5rem 1rem; }}
    .spotlight-block {{ background: #fff8e1; border-left: 4px solid #f5a623;
                         border-radius: 6px; padding: 1.25rem; margin-bottom: 2rem; }}
    .spotlight-block h2 {{ font-size: 1.1rem; color: #b8860b; margin-bottom: 0.25rem; }}
    .spotlight-block .subtitle {{ font-size: 0.8rem; color: #888; margin-bottom: 1rem; }}
    .day-heading {{ font-size: 1rem; font-weight: 700; color: #444;
                    border-bottom: 1px solid #ddd; padding-bottom: 0.4rem;
                    margin: 1.5rem 0 0.75rem; }}
    .card {{ background: white; border-radius: 6px; padding: 1rem;
              margin-bottom: 0.75rem; box-shadow: 0 1px 3px rgba(0,0,0,.07); }}
    .card.spotlight {{ border-left: 3px solid #f5a623; }}
    .card-header {{ display: flex; align-items: flex-start; gap: 0.5rem; flex-wrap: wrap; }}
    .card h3 {{ font-size: 0.95rem; font-weight: 600; flex: 1; }}
    .card h3 a {{ color: #1a1a2e; text-decoration: none; }}
    .card h3 a:hover {{ text-decoration: underline; }}
    .badge {{ background: #f5a623; color: white; font-size: 0.7rem;
               font-weight: 700; padding: 0.15rem 0.4rem; border-radius: 3px;
               white-space: nowrap; }}
    .meta {{ font-size: 0.8rem; color: #666; margin-top: 0.4rem;
              display: flex; flex-wrap: wrap; gap: 0.75rem; }}
    .price {{ font-weight: 600; color: #2d6a4f; }}
    .desc {{ font-size: 0.82rem; color: #555; margin-top: 0.5rem; }}
    footer {{ text-align: center; font-size: 0.75rem; color: #aaa;
               padding: 2rem 1rem; }}
  </style>
</head>
<body>
  <header>
    <h1>Jackson Heights Insider — Events</h1>
    <p>Updated {today.strftime("%A, %B %d, %Y")} · Source: <a href="{BASE_URL}" style="color:#aaa">{BASE_URL}</a></p>
  </header>
  <main>
    {spotlight_section}
    {"".join(day_sections)}
  </main>
  <footer>Auto-generated daily · <a href="{BASE_URL}">Jackson Heights Insider</a></footer>
</body>
</html>"""

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"  Saved → {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print("── Step 1: Pulling data ──────────────────────────────────")
    pages_html = fetch_pages()
    if not pages_html:
        print("No pages fetched. Exiting.")
        return 1
    print(f"  {len(pages_html)} page(s) fetched")

    print("\n── Step 2: Cleaning into structured events ───────────────")
    all_events: list[Event] = []
    for html in pages_html:
        batch = parse_events(html)
        all_events.extend(batch)
    print(f"  {len(all_events)} total event(s) parsed")

    print("\n── Step 3: Filtering for tomorrow ────────────────────────")
    tomorrow_events = filter_tomorrow(all_events)

    print_events(tomorrow_events)

    stamp = date.today().strftime("%Y-%m-%d")
    if tomorrow_events:
        save_json(tomorrow_events, f"events_tomorrow_{stamp}.json")

    save_text(all_events, f"events_all_{stamp}.txt")
    save_html(all_events, "docs/index.html")

    return 0


if __name__ == "__main__":
    sys.exit(main())

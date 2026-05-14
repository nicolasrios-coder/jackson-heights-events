# Jackson Heights Event Pipeline

A daily scraper that pulls community events from [Jackson Heights Insider](https://jacksonheightsinsider.com/events), structures them, highlights events relevant to immigrant and Latin American communities, and publishes a live webpage updated every day.

**Live page → [nicolasrios-coder.github.io/jackson-heights-events](https://nicolasrios-coder.github.io/jackson-heights-events/)**

---

## What it pulls

Source: `https://jacksonheightsinsider.com/events`

The site runs on the **The Events Calendar** WordPress plugin. The scraper targets each event's structured markup and extracts:

| Field | Source |
|---|---|
| Title | `tribe-events-calendar-list__event-title` |
| Date | `tribe-event-date-start` |
| Start / end time | `tribe-event-date-start` + `tribe-event-time` |
| Venue + address | `tribe-events-calendar-list__event-venue-title` |
| Description | `tribe-events-calendar-list__event-description` |
| Price | `tribe-ticket-cost` / `tribe-cost` |
| Link | Title anchor href |

---

## When it runs

The pipeline is triggered automatically by **GitHub Actions** every day at **2:00 pm Eastern Time** (18:00 UTC in summer / EDT).

```yaml
on:
  schedule:
    - cron: "0 18 * * *"
  workflow_dispatch:       # can also be triggered manually from the Actions tab
```

GitHub runs this on their servers — no local machine needs to be on.

Each run:
1. Scrapes the events page
2. Filters for tomorrow's events
3. Generates an updated `docs/index.html` (published to GitHub Pages)
4. Commits the dated `.txt` and `.json` output files back to the repo as an archive
5. Deploys the updated page

---

## Community filter

Events are automatically flagged and surfaced at the top of the page if they match any of the following signals:

**Spanish-language detection**
Any accented character (`á é í ó ú ü ñ ¿ ¡`) in the title, description, venue, or address triggers the flag. This catches Spanish-language content reliably without keyword matching.

**Immigrant & migrant terms**
`immigrant` · `immigrants` · `inmigrante` · `inmigrantes` · `migrante` · `migrantes` · `undocumented` · `indocumentado` · `asylum` · `asilo`

**Language & identity**
`spanish` · `español` · `bilingual` · `bilingüe` · `latin` · `latino` · `latina` · `latinx` · `hispanic` · `hispano`

**Latin American countries** (English + Spanish names)
Mexico · Guatemala · Honduras · El Salvador · Nicaragua · Costa Rica · Panama · Cuba · Dominican Republic · Puerto Rico · Colombia · Venezuela · Ecuador · Peru · Bolivia · Chile · Argentina · Uruguay · Paraguay · Brazil · Haiti

**Cultural & community keywords**
`folklórico` · `zumba` · `cumbia` · `salsa` · `merengue` · `bachata` · `mariachi` · `tango` · `comunidad` · `vecinos` · `gratis` · `clases` · `talleres` · and more

Flagged events appear under a **★ Community Spotlight** section at the top of both the webpage and the daily `.txt` file, marked with `>>>`.

---

## Output files

Each daily run produces:

| File | Contents |
|---|---|
| `docs/index.html` | GitHub Pages site — all events with community spotlight |
| `events_all_YYYY-MM-DD.txt` | Plain text — all events grouped by day |
| `events_tomorrow_YYYY-MM-DD.json` | Structured JSON — tomorrow's events only |

---

## Run locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the pipeline
cd event-pipeline
python pipeline.py
```

Outputs are written to the current directory.

---

## Built by

[Documented](https://documentedny.com) — New York City's nonprofit newsroom covering immigration.

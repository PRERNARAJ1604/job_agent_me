"""
internshala.py — Internshala "fresher jobs" source.

Why this exists: Internshala's /fresher-jobs/ section lists only jobs open
to freshers (most cards literally say "No experience required"), which the
big boards bury under senior postings. Confirmed live 2026-10: 23 distinct
genuine fresher jobs in Bangalore across the categories below ("Junior
Software Engineer", "Associate Software Developer", "Python Developer"...).

There is no public API — this parses the server-rendered listing HTML, so
it can break if Internshala redesigns. Every request is individually
guarded (like naukri_playwright.py): a failed page/category is logged and
skipped, never fatal. Things verified against the live HTML that this
depends on:

- Listing pages mix in promoted INTERNSHIPS; each card carries
  employment_type="job"|"internship" — only "job" cards are kept.
- After the genuine matches, a "no_opening_banner" ("No more results found
  matching the profile and location filter. Check out other opportunities
  below!") is followed by UNRELATED jobs — everything after it is ignored.
- An unknown category slug silently redirects to ALL jobs in the city
  (e.g. java-development -> /fresher-jobs/jobs-in-bangalore/) — detected
  via the final URL and skipped.

Like unstop.py, postings stay up for weeks, so this uses its own 14-day
age ceiling instead of the sweep's hours_old window, and relies on
pipeline.sweep()'s URL dedup to surface each posting only once.
"""

import re
import html
import time
import random
import logging
from datetime import datetime, timezone, timedelta

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://internshala.com"
LISTING_URL = BASE_URL + "/fresher-jobs/{category}-jobs-in-{city}/"
# Category slugs verified live (2026-10) to return genuine fresher matches
# for this resume's stack; overlapping categories are fine — results are
# de-duplicated by job URL.
CATEGORIES = [
    "software-development", "java", "backend-development",
    "full-stack-development", "web-development", "python", "sql",
    "computer-science", "data-analytics",
]
MAX_AGE_DAYS = 14
MIN_DAYS_TO_DEADLINE = 2
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}


def _text(fragment):
    fragment = re.sub(r"<(br|/p|/li|/div|/h\d)[^>]*>", "\n", fragment or "", flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", " ", fragment))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()


def _first(pattern, fragment):
    m = re.search(pattern, fragment, re.S)
    return _text(m.group(1)) if m else ""


def _age_days(posted):
    # "Just now", "Today", "Few hours ago", "4 days ago", "1 week ago", "2 months ago"
    posted = posted.lower()
    m = re.search(r"(\d+)\s*(day|week|month)", posted)
    if not m:
        return 0 if re.search(r"just now|today|hour|minute", posted) else None
    return int(m.group(1)) * {"day": 1, "week": 7, "month": 30}[m.group(2)]


def _salary(text):
    # Listing shows "₹ 3,00,000 - 4,00,000" (annual) or "₹ 15,000 - 18,000 /month".
    # Annual is formatted as "N-M LPA" so pipeline.salary_to_lpa() parses it.
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text)]
    if not nums:
        return None
    if "month" in text.lower():
        return f"Rs {nums[0]:,}" + (f"-{nums[-1]:,}" if nums[-1] != nums[0] else "") + " per month"
    lo, hi = nums[0] / 100000, nums[-1] / 100000
    return f"{lo:g}-{hi:g} LPA" if lo != hi else f"{lo:g} LPA"


def _experience_sentence(label):
    # Folded into the description so pipeline.should_keep()'s experience
    # filter sees it: "No experience required" -> "0 years experience.",
    # "0-2 year(s)" -> "0-2 years experience."
    if re.search(r"no experience|fresher", label, re.I):
        return "0 years experience."
    m = re.search(r"(\d+)\s*-\s*(\d+)", label)
    if m:
        return f"{m.group(1)}-{m.group(2)} years experience."
    m = re.search(r"(\d+)", label)
    return f"{m.group(1)} years experience." if m else ""


def _parse_listing(page_html):
    # Everything after the "no more results" banner is unrelated filler.
    genuine = page_html.split("no_opening_banner")[0]
    cards = re.split(r'(?=<div[^>]*class="[^"]*individual_internship\s)', genuine)
    jobs = []
    for card in cards:
        head = card[:600]
        if 'employment_type="job"' not in head:
            continue
        href = re.search(r"data-href='([^']+)'", head)
        if not href:
            continue
        jobs.append({
            "url": BASE_URL + href.group(1),
            "title": _first(r'class="job-title-href"[^>]*>(.*?)</a>', card),
            "company": _first(r'class="company-name"[^>]*>(.*?)</p>', card),
            "location": _first(r'class="row-1-item locations".*?<span>(.*?)</span>', card),
            "salary": _first(r'<span class="desktop">(.*?)</span>', card),
            "experience": _first(r'ic-16-briefcase"></i>\s*<span>(.*?)</span>', card),
            "posted": _first(r'ic-16-reschedule"></i>\s*<span>(.*?)</span>', card),
            "skills": [_text(s) for s in re.findall(r"class='job_skill'>(.*?)</div>", card)],
        })
    return jobs


def _fetch_detail(url):
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    page = resp.text
    i = page.find('class="internship_details"')
    i = page.find(">", i) + 1 if i >= 0 else -1  # skip past the opening tag itself
    description = _text(page[i:i + 15000]) if i > 0 else ""
    # Cut the trailing "Activity on Internshala / Apply now / ..." page chrome.
    description = re.split(r"\bActivity on Internshala\b", description)[0]
    apply_by = None
    m = re.search(r"Apply By\s*(?:<[^>]+>\s*)*(\d{1,2}\s+\w{3}'?\s*\d{2})", page, re.I)
    if m:
        try:
            apply_by = datetime.strptime(m.group(1).replace("'", "").replace("  ", " "), "%d %b %y").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return description, apply_by


def scrape_internshala(locations):
    """Scrape each category's fresher-jobs page per city in `locations`,
    returning raw job dicts in the same shape career_sites._raw() produces."""
    now = datetime.now(timezone.utc)
    seen, results = set(), []

    for city in locations:
        city_slug = re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")
        for category in CATEGORIES:
            url = LISTING_URL.format(category=category, city=city_slug)
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("Internshala listing failed for %s: %s", url, e)
                continue
            if not resp.url.rstrip("/").endswith(f"{category}-jobs-in-{city_slug}"):
                logger.warning("Internshala category %r redirected to %s — slug no longer valid, skipped", category, resp.url)
                continue

            for card in _parse_listing(resp.text):
                if card["url"] in seen:
                    continue
                seen.add(card["url"])
                age = _age_days(card["posted"])
                if age is not None and age > MAX_AGE_DAYS:
                    continue
                try:
                    description, apply_by = _fetch_detail(card["url"])
                except Exception as e:
                    logger.warning("Internshala detail failed for %s: %s — using card summary only", card["url"], e)
                    description, apply_by = "", None
                if apply_by and (apply_by - now) < timedelta(days=MIN_DAYS_TO_DEADLINE):
                    continue

                parts = [_experience_sentence(card["experience"])]
                if card["skills"]:
                    parts.append("Skills: " + ", ".join(card["skills"]) + ".")
                parts.append(description)
                results.append({
                    "title": card["title"],
                    "company": card["company"],
                    "location": re.sub(r"bengaluru", "Bangalore", card["location"] or city, flags=re.IGNORECASE),
                    "description": " ".join(p for p in parts if p),
                    "url": card["url"],
                    "salary": _salary(card["salary"]),
                    "board": f"internshala · apply by {apply_by:%d %b}" if apply_by else "internshala",
                    "company_size": 0,
                    "age_hours": age * 24 if age is not None else None,
                })
                time.sleep(random.uniform(0.5, 1.5))
            time.sleep(random.uniform(1, 2))

    logger.info("Internshala: %d fresher jobs across %d categories", len(results), len(CATEGORIES))
    return results

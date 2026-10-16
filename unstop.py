"""
unstop.py — Unstop (unstop.com) job source, fresher-focused.

Why this exists: Indeed/LinkedIn/Naukri skew heavily towards experienced
postings even with "fresher" in the query (confirmed live 2026-10: a plain
"Software Engineer" LinkedIn search for Bengaluru was 8/10 senior titles).
Unstop is a graduate/early-career platform — most of its job postings
target freshers — and exposes a free, public, unauthenticated JSON search
API, so no browser/anti-bot handling is needed (unlike naukri_playwright.py).

Every posting carries an audience tag in `filters` ("Fresher",
"Experienced Professionals", "All") — postings tagged ONLY "Experienced
Professionals" are dropped here, before pipeline.should_keep() runs the
usual role/keyword/experience/location filters on the rest.

Unstop postings stay open for weeks with an explicit application deadline,
so (like career_sites.py's watchlist) this ignores the per-trigger
hours_old window in favour of its own limits (MAX_AGE_DAYS,
MIN_DAYS_TO_DEADLINE below) and relies on pipeline.sweep()'s URL dedup to
surface each posting only once. The deadline is shown in the digest via
the `board` column ("unstop · apply by 28 Oct") — no DB schema change needed.
"""

import re
import html
import time
import random
import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://unstop.com/api/public/opportunity/search-result"
PER_PAGE = 30
MAX_PAGES_PER_TERM = 3
# Same 14-day ceiling as career_sites.WATCHLIST_MAX_AGE_HOURS — fresher
# postings fill fast. And skip postings closing within 2 days: by the time
# the digest is read and a resume sent, they're effectively closed.
MAX_AGE_DAYS = 14
MIN_DAYS_TO_DEADLINE = 2
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json",
}

# Unstop's search is already fresher-skewed and matches on title words —
# "Java Developer Fresher" returns far fewer hits than "Java Developer"
# because few titles literally contain "Fresher". Strip these before
# querying; the audience-tag filter below does that job instead.
_QUERY_NOISE = re.compile(r"\b(fresher|freshers|entry level|graduate|trainee|2026 batch)\b", re.IGNORECASE)


def _query_for(role):
    return re.sub(r"\s+", " ", _QUERY_NOISE.sub(" ", role)).strip() or role


def _parse_dt(text):
    # approved_date: "2026-10-14 16:44:24 GMT+0530"; end_date: ISO 8601.
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S GMT%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _strip_html(text):
    text = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", text or "", flags=re.IGNORECASE)
    return html.unescape(re.sub(r"<[^>]+>", " ", text))


def _salary(job_detail):
    # Formatted as "N-M LPA" so pipeline.salary_to_lpa() parses it the same
    # way it parses Naukri's "Lacs PA" strings. Monthly figures (stipend-
    # style postings) stay unlabelled-currency text, which salary_to_lpa()
    # deliberately returns None for — never blocks a job.
    if not job_detail.get("show_salary") or job_detail.get("not_disclosed"):
        return None
    lo, hi = job_detail.get("min_salary"), job_detail.get("max_salary")
    if not lo and not hi:
        return None
    lo, hi = lo or hi, hi or lo
    if job_detail.get("pay_in") == "annually":
        return f"{lo / 100000:g}-{hi / 100000:g} LPA" if lo != hi else f"{lo / 100000:g} LPA"
    period = {"monthly": "month", "weekly": "week", "daily": "day", "hourly": "hour"}.get(job_detail.get("pay_in"), "month")
    amount = f"Rs {lo:,}" if lo == hi else f"Rs {lo:,}-{hi:,}"
    return f"{amount} per {period}"


def _location(job_detail):
    cities = [c for c in (job_detail.get("locations") or []) if isinstance(c, str)]
    location = ", ".join(cities)
    if job_detail.get("type") == "wfh":
        location = f"Remote{', ' + location if location else ''}"
    # Same Bengaluru -> Bangalore normalization career_sites.py needs, or
    # pipeline.location_matches() rejects every Bengaluru posting.
    return re.sub(r"bengaluru", "Bangalore", location or "India", flags=re.IGNORECASE)


def _to_raw(opp, now):
    job_detail = opp.get("jobDetail") or {}
    skills = [s.get("skill_name") or s.get("skill") for s in (opp.get("required_skills") or [])]
    audience = [f.get("name") for f in (opp.get("filters") or []) if f.get("name")]

    # Folded into the description so pipeline.should_keep()'s keyword and
    # experience filters (which only read title + description) see them.
    parts = []
    lo_exp, hi_exp = job_detail.get("min_experience"), job_detail.get("max_experience")
    if lo_exp is not None or hi_exp is not None:
        parts.append(f"{lo_exp or 0}-{hi_exp if hi_exp is not None else lo_exp} years experience.")
    if skills:
        parts.append("Skills: " + ", ".join(s for s in skills if s) + ".")
    if audience:
        parts.append("Eligible: " + ", ".join(audience) + ".")
    parts.append(_strip_html(opp.get("details")))

    approved = _parse_dt(opp.get("approved_date"))
    end = _parse_dt(opp.get("end_date"))
    return {
        "title": opp.get("title") or "",
        "company": (opp.get("organisation") or {}).get("name") or "",
        "location": _location(job_detail),
        "description": " ".join(parts),
        "url": opp.get("seo_url") or "",
        "salary": _salary(job_detail),
        "board": f"unstop · apply by {end:%d %b}" if end else "unstop",
        "company_size": 0,  # not exposed by the API
        "age_hours": (now - approved).total_seconds() / 3600 if approved else None,
    }


def _is_candidate(opp, now):
    if not opp.get("regn_open"):
        return False
    end = _parse_dt(opp.get("end_date"))
    if end and (end - now).total_seconds() < MIN_DAYS_TO_DEADLINE * 86400:
        return False
    approved = _parse_dt(opp.get("approved_date"))
    if approved and (now - approved).total_seconds() > MAX_AGE_DAYS * 86400:
        return False
    audience = {f.get("name") for f in (opp.get("filters") or [])}
    if audience and audience <= {"Experienced Professionals"}:
        return False
    return True


def scrape_unstop(roles):
    """Search Unstop once per role (de-duplicated queries), returning raw job
    dicts in the same shape career_sites._raw() produces. Each request is
    individually guarded — one failed page/term doesn't lose the rest."""
    now = datetime.now(timezone.utc)
    seen_ids, results = set(), []
    queries = list(dict.fromkeys(_query_for(r) for r in roles))

    for query in queries:
        for page in range(1, MAX_PAGES_PER_TERM + 1):
            try:
                resp = requests.get(SEARCH_URL, headers=_HEADERS, timeout=30, params={
                    "opportunity": "jobs", "oppstatus": "open", "searchTerm": query,
                    "per_page": PER_PAGE, "page": page,
                })
                resp.raise_for_status()
                data = resp.json()["data"]
            except Exception as e:
                logger.warning("Unstop search failed for %r page %d: %s", query, page, e)
                break

            for opp in data.get("data") or []:
                if opp.get("id") in seen_ids or not _is_candidate(opp, now):
                    continue
                seen_ids.add(opp.get("id"))
                results.append(_to_raw(opp, now))

            if page >= (data.get("last_page") or 1):
                break
            time.sleep(random.uniform(1, 2))

    logger.info("Unstop: %d open fresher-eligible postings across %d queries", len(results), len(queries))
    return results

# Set up the job agent for yourself

This repo runs a job search for you on GitHub's servers, about 12 times a day.
It searches job sites, keeps the postings that match **your** resume and
target roles, writes a tailored one-page resume for each of the best ones, and
emails you a digest with those resumes attached. It never applies for you —
you apply yourself.

Right now it is set up for **one specific person: a fresher (0–1 years) looking
for Software Developer / Java backend / entry-level Data Analyst roles in
Bangalore**. To use it yourself you copy it, then replace that person's resume,
skills and preferences with your own. Budget **1–2 hours** for the first setup.

**What you need**
- A GitHub account.
- A Gmail account to send the emails from (with 2-Step Verification).
- Free API keys from Groq and Google AI Studio (step 5).
- Microsoft Word or similar, to edit a `.docx` resume.
- Comfort editing a few Python lists in a text editor. No other coding needed.
  Python on your own computer is optional (only for testing locally).

**Contents**
1. [Copy the repo](#1-copy-the-repo)
2. [Reset the job history](#2-reset-the-job-history)
3. [Replace the resume](#3-replace-the-resume)
4. [Tell it what you're looking for](#4-tell-it-what-youre-looking-for)
5. [Get the API keys and Gmail app password](#5-get-the-api-keys-and-gmail-app-password)
6. [Add the GitHub secrets](#6-add-the-github-secrets)
7. [Turn on the workflows and test](#7-turn-on-the-workflows-and-test)
8. [Keeping it running](#8-keeping-it-running)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Copy the repo

**Option A — Fork (simplest).** Click **Fork** on the repo page. A fork of a
public repo is **always public**: anyone can download your resume (name, phone,
email) from it.

**Option B — Private copy.** Go to <https://github.com/new/import>, paste this
repo's URL, choose **Private**. Your resume stays private, **but** GitHub only
gives private repos 2,000 free Actions minutes a month, and this agent uses
roughly **4,400** (measured: ~146 minutes a day). To stay free, cut the
schedule to under half (see [Changing the schedule](#changing-the-schedule))
or pay for extra minutes.

Public repos get unlimited free minutes.

---

## 2. Reset the job history

`data/jobs.db` holds every job already sent to the previous owner. The agent
**never sends a job it has seen before**, so if you keep this file you will
silently miss those jobs. Delete it:

- On GitHub: open `data/jobs.db` → **⋯** → **Delete file** → commit.

The first run creates a fresh one automatically.

---

## 3. Replace the resume

The agent rewrites only two sections of your resume per job — **Summary** and
**Skills** — and leaves everything else exactly as you wrote it. To do that it
relies on the file's structure, so follow these rules.

**Easiest way:** open the existing `resume_base.docx` in Word, overwrite the
text with yours (keep the formatting), save, and upload it back to the repo
with the same name. A resume built in a different template usually works too,
as long as it follows the rules below.

**Rules (the code depends on these):**

| Part | Rule |
|---|---|
| Section headings | Short lines in **ALL CAPS** (e.g. `WORK EXPERIENCE`), or real Word "Heading" styles. Any other short all-caps line will be mistaken for a heading — avoid those. |
| Summary heading | Text exactly `PROFESSIONAL SUMMARY`, `SUMMARY` or `PROFILE`. |
| Summary body | **One paragraph**, directly followed by the next heading — **no empty line** between them (an empty line ends the section early). Don't start it with a bold phrase: the rewritten summary copies the formatting of its first words, so the whole summary would turn bold. |
| Skills heading | Text exactly `SKILLS`, `TECHNICAL SKILLS` or `CORE SKILLS`. |
| Skill lines | One line per category, written `Category: skill, skill, skill`, with the `Category:` part in **bold** and the skills not bold. Category names must not be all caps. |
| Layout | Single column. **No tables, text boxes, columns, or anything in the page header/footer** — many recruiter systems (ATS) can't read those, and the agent flags them. |
| Length | One page, with **about 5–6 blank lines spare at the bottom**. Tailoring can lengthen the summary (capped at 75 words) and add up to 6 skills, sometimes as a new skill line. |

**Then check the skill categories match.** Open `skills_editor.py`, find
`category_mapping()`. Its keys (`"Languages"`, `"Databases & Caching"`, …) must
be **exactly** your resume's category names, and each list holds lowercase
words that belong in that category. A skill the agent adds lands in the first
category whose list contains part of its name, so put specific categories
first (e.g. databases before languages, or "postgresql" would match "sql").

---

## 4. Tell it what you're looking for

Almost everything lives in **`job_filters.py`**. Each setting has a comment
explaining it; these are the ones you must change:

| Setting | What it does | What to put |
|---|---|---|
| `TARGET_ROLES` | The search terms sent to every job site, once per city. | 4–6 terms. Seniority words in the term help a lot: "SDE 1" or "Java Developer Fresher" return far fewer senior jobs than "Software Engineer". |
| `ROLE_WORD_GROUPS` | Which job **titles** are accepted. A title passes if it contains all the words of any one group, in any order. | Groups covering how your target roles are actually titled. |
| `EXCLUDED_ROLE_PHRASES` | Titles containing these are always rejected. | Roles you don't want (e.g. "qa", "sales engineer"). |
| `LOCATIONS` | Cities searched. | Your cities, spelled as job sites write them ("Bangalore", not "Bengaluru"). |
| `INCLUDE_REMOTE` | Also search and accept remote jobs. | `True` or `False`. |
| `MATCH_KEYWORDS` | The skills used to judge whether a job fits you. **Also the only skills tailoring may add to your resume.** | Lowercase. **Only skills genuinely on your resume** — anything here can end up on a tailored resume. |
| `CORE_SKILLS` | Your main skills; count 3× when ranking jobs. | A subset of `MATCH_KEYWORDS`. |
| `PROGRAMMING_SKILLS` | A job must mention at least one of these. | Your languages/frameworks. For a non-programming career, put your must-have skills here. |
| `TITLE_ONLY_BLOCKED_KEYWORDS` | Titles containing these are rejected. | Currently blocks senior titles (senior, lead, manager, II, III…) and internships. **If you're experienced, remove the seniority words.** |
| `MAX_EXPERIENCE_YEARS` | Rejects jobs whose stated experience **starts above** this (e.g. "2–5 years" when set to 1). | Your years of experience, plus some slack. |
| `FRESHER_SIGNALS` / `FRESHER_BONUS` | Ranks jobs higher when the description says "fresher", "0–1 years" etc. | Set `FRESHER_BONUS = 0` if you're not a fresher. |

**Also change these (they're written about the current person):**

- **`summary_generator.py` → `_static_fallback_summary()`**: the summary used
  if both AI services fail. Rewrite it about yourself. In the same file,
  `_DISPLAY_CASE` maps skills to their proper capitalization
  (`"postgresql": "PostgreSQL"`) — add yours.
- **`profile_loader.py`**: a short education/experience description. Replace it
  with yours (cosmetic — the AI reads your actual resume).
- **`career_sites.py`**: a hand-picked list of company career sites checked
  directly (Greenhouse, Lever, Workday…), chosen for tech companies hiring in
  India. Remove ones irrelevant to you. Adding a company needs its exact
  board/tenant name, so test before relying on it.

**If you're not a fresher — sources and filters built for freshers:**

| Where | Fresher-specific part | For an experienced search |
|---|---|---|
| `naukri_playwright.py` → `SEARCH_URL` | `?experience=0` — Naukri only returns jobs open to 0 years | Change to your years, e.g. `?experience=5` |
| `.github/workflows/job_sweep.yml` → `--sites` | `unstop` and `internshala` are fresher/graduate job boards | Remove them from the list |
| `internshala.py` → `CATEGORIES` | Internshala job categories for a software/data profile | Change to yours, or drop the source |
| Experience filter | Only a **maximum** (`MAX_EXPERIENCE_YEARS`) | There's no minimum filter today. The repo's history (before the "Retarget job agent to Prerna Raj's resume" commit) has the earlier version that rejected postings below a minimum — restore that check in `pipeline.should_keep()` |

---

## 5. Get the API keys and Gmail app password

**Groq** (writes the tailored summaries) — <https://console.groq.com/keys> →
sign up → **Create API Key** → copy it. Free, no card needed.

**Gemini** (backup when Groq is busy) — <https://aistudio.google.com/apikey> →
**Create API key** → copy it. Free.

**Gmail app password** (sends the emails). Use the Gmail account the emails
should come **from**:
1. Turn on 2-Step Verification:
   <https://myaccount.google.com/signinoptions/twosv>.
2. Go to <https://myaccount.google.com/apppasswords>, name it `Job Agent`,
   click **Create**, and copy the 16-letter code. Google shows it only once.
   If the page says the setting isn't available, 2-Step Verification is still off.

An app password doesn't expire (unless you change your Google password). You
don't need Google Cloud, OAuth, or `credentials.json`/`token.json` — those are
only an optional fallback (see the last row of the table in
[section 6](#6-add-the-github-secrets)).

---

## 6. Add the GitHub secrets

In your repo: **Settings → Secrets and variables → Actions → New repository
secret**, once per row. Names must match exactly.

| Secret | Required? | Value |
|---|---|---|
| `GMAIL_APP_PASSWORD` | **Yes** | The 16-letter app password (spaces are fine). |
| `JOB_EMAIL` | **Yes** | The Gmail address the app password belongs to — the **sender**. |
| `NOTIFY_EMAIL` | **Yes** | Where the reports go (can be the same address). |
| `GROQ_API_KEY` | **Yes** | From step 5. |
| `GEMINI_API_KEY` | **Yes** | From step 5. |
| `FIRST_NAME`, `LAST_NAME` | **Yes** | Used in the attachment file names (`FirstLast_Role_Company.docx`). |
| `PHONE`, `LINKEDIN_URL`, `GITHUB_URL` | Optional | Your details. |
| `MIN_SALARY_LPA` | Optional | Skip jobs whose stated salary **ceiling** is below this many lakhs per year. Leave unset for no floor. |
| `YEARS_EXP`, `SALARY_LPA`, `EXPERIENCE_LEVEL` | Optional | Profile details. |
| `PROXIES` | Optional | Only if you've bought rotating proxies. |
| `GMAIL_TOKEN_B64`, `GMAIL_CREDENTIALS` | Optional | Old Google Cloud OAuth login, used only if the app password fails. Not needed. |

**Tip:** GitHub hides secret values everywhere in the logs. A secret set to a
very short value like `0` makes every "0" in the logs show as `***`. Leave
optional numeric secrets unset rather than setting them to `0`.

---

## 7. Turn on the workflows and test

1. Open your repo's **Actions** tab. On a fork GitHub shows *"Workflows aren't
   being run on this forked repository"* — click **I understand my workflows,
   go ahead and enable them**.
2. Each of the three workflows (Indeed, LinkedIn, Naukri) may show a
   *"scheduled workflows are disabled"* banner — open each one and click
   **Enable workflow**.
3. Run one by hand: **Job Agent — Indeed Sweep → Run workflow → Run workflow**.
   It takes 5–20 minutes.
4. Open the finished run → **sweep** → **Run cloud pipeline**, and check:

| Log line | Meaning |
|---|---|
| `Sweep complete: N new jobs saved` | Jobs that passed your filters. **0 on the first run usually means your filters are too strict** — see section 9. |
| `Email report sent to … (SMTP, app password)` | Email works. Check spam/promotions the first time. |
| `Nothing to tailor or email this cycle.` | No new matching jobs this run, so no email. Normal later on; not normal on the very first run. |
| `Gmail rejected the app password` | The app password was created on a different Gmail account than `JOB_EMAIL`, or was copied wrong. |
| `Groq summary generation failed, falling back to Gemini` | Fine occasionally. Every time means a bad Groq key. |

5. Open one attached resume and check the Summary and Skills look right, and
   that nothing else moved.

After that it runs by itself on schedule.

---

## 8. Keeping it running

- **Every ~60 days, make any commit** (even a one-word README edit). GitHub
  pauses scheduled workflows after 60 days without repository activity, and
  the bot's own database commits don't seem to count. If it happens, the
  Actions tab shows a yellow banner with an **Enable workflow** button.
- **If an email suddenly has far fewer jobs**, a job site has probably changed
  its pages or started blocking (Naukri and Internshala are the most fragile).
  The run log will show warnings from that source.
- **If summaries stop being AI-written**, the AI provider may have retired the
  model. Model names are in `config.py` (`GROQ_MODEL`, `GEMINI_MODEL`); check
  the provider's deprecations page for the replacement.

### Changing the schedule

Each workflow file in `.github/workflows/` has its run times as `cron:` lines,
in **UTC** (IST = UTC + 5:30). Each run only looks at jobs posted since that
workflow's previous run, using the **"Determine hours_old for this trigger"**
table further down the same file. **If you add, remove or move a `cron:` line,
update that table too**, or you'll miss jobs (window too short) or get repeats
(too long).

---

## 9. Troubleshooting

| Problem | Likely cause / fix |
|---|---|
| First run finds 0 jobs | Filters too strict. In `job_filters.py`, widen `ROLE_WORD_GROUPS`, check `LOCATIONS` spelling, make sure `MATCH_KEYWORDS`/`PROGRAMMING_SKILLS` include skills real job ads use, and check `TITLE_ONLY_BLOCKED_KEYWORDS` isn't blocking your level. |
| Jobs found but no email | Look for `Email sent: False` in the log, plus the line above it saying why. Usually the app password or `JOB_EMAIL`. |
| Emails were arriving, then stopped | No new matches (normal), the workflows were paused (60-day rule), or the Google password was changed (that revokes app passwords). |
| Tailored resume has a blank or merged section | The resume breaks one of the rules in section 3 — usually an empty line under the summary, or a heading that isn't all caps. |
| Tailored resume runs to 2 pages | Not enough spare space at the bottom of your base resume — free up ~5–6 lines. |
| Wrong skills added to the resume | `MATCH_KEYWORDS` contains a skill you don't have — remove it. |
| A job-site warning appears every run | That site is blocking or changed its layout. The run still completes with the other sources. |

### Testing on your own computer (optional)

```bash
pip install -r requirements_cloud.txt
playwright install chromium          # only needed for Naukri
cp .env.example .env                 # then fill in your values
python cloud_run.py --sites indeed,unstop --hours-old 24
```

This is a real run: it **sends a real email**. It keeps its own local copy of
`data/jobs.db`, separate from GitHub's, so the scheduled runs may send you the
same jobs again later.

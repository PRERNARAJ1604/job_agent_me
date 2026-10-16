"""
job_filters.py — Role/location/keyword filtering criteria.

Pulled out of scraper.py so the cloud pipeline (pipeline.py -> cloud_run.py)
can import filter criteria without dragging in scraper.py's Playwright
dependency, which the jobspy-based cloud scrape no longer needs.

Retargeted 2026-10 to Prerna Raj's resume (resume_base.docx): fresher /
0-1 year Software Developer, Java/Backend Developer and entry-level Data
Analyst roles. The previous candidate's resume is kept as
resume_base_aman_backup.docx (not used by the pipeline).
"""

# Search terms actually sent to jobspy/Naukri/Unstop as `search_term` —
# what gets queried. Each term is multiplied by every location (and every
# site), so keep this list short. Chosen from a live LinkedIn test
# (2026-10, Bengaluru, past week): plain "Software Engineer" returned 8/10
# senior titles, while each term below returned 0 senior titles in its
# first 10-20 results. LinkedIn's public search IGNORES its entry-level
# filter (f_E) — identical results with and without it — so the seniority
# signal has to come from the query words themselves.
TARGET_ROLES = [
    "SDE 1",
    "Associate Software Engineer",
    "Trainee Software Engineer",
    "Graduate Engineer Trainee",
    "Java Developer Fresher",
    "Data Analyst Fresher",
]

# Title-acceptance rule used by pipeline.role_matches(): a posting is kept
# if its title contains ALL words in at least one group below, in ANY order
# and not necessarily adjacent. Word-based rather than literal-phrase
# matching on purpose — real postings phrase the same role differently
# ("Software Engineer - Backend" vs "Backend Software Engineer"). Still
# gated by the MATCH_KEYWORDS/MIN_MATCH_COUNT floor below, so this doesn't
# admit irrelevant roles just from title words alone.
ROLE_WORD_GROUPS = [
    # Software developer / engineer
    {"software", "developer"},
    {"software", "engineer"},
    # "engineering"/"development" are separate words to the matcher —
    # confirmed live, fresher titles like "Specialist I - Software
    # Engineering" and "Associate - Software Engineering" were rejected.
    {"software", "engineering"},
    {"software", "development"},
    {"software", "trainee"},
    {"software", "apprentice"},
    {"graduate", "engineer"},
    {"engineer", "trainee"},
    {"sde"},
    {"sde1"},
    {"application", "developer"},
    {"programmer", "analyst"},
    {"developer", "trainee"},
    # Backend / Java
    {"backend", "developer"},
    {"backend", "engineer"},
    {"back end", "developer"},
    {"back-end", "developer"},
    {"java", "developer"},
    {"java", "engineer"},
    {"spring boot", "developer"},
    {"python", "developer"},
    {"full stack", "developer"},
    {"fullstack", "developer"},
    # Entry-level data analyst
    {"data", "analyst"},
    {"database", "analyst"},
    {"reporting", "analyst"},
    {"mis", "analyst"},
    {"analytics", "associate"},
]

# Titles containing one of these phrases are rejected outright even if a
# ROLE_WORD_GROUPS group matches — e.g. "Software Test Engineer" matches
# {"software","engineer"} but is a QA role, not a development one.
EXCLUDED_ROLE_PHRASES = [
    "data scientist", "machine learning engineer", "ml engineer",
    "qa", "test engineer", "testing", "sdet", "automation tester",
    "support engineer", "sales engineer", "embedded", "mainframe", "sap",
]
EXCLUDED_ROLE_REDEEMERS = set()

# Candidate is Bengaluru-based. Remote is always added on top of these by
# pipeline.sweep() / location_matches().
LOCATIONS = ["Bangalore", "Hyderabad", "Pune"]

# Aligned to Prerna's actual resume (resume_base.docx) — real stack only,
# so the confidence score reflects genuine fit and jd_analyzer never feeds
# the tailoring step a skill she doesn't have. Every entry below appears in
# her Skills, Experience or Projects sections.
MATCH_KEYWORDS = [
    # Languages
    "java", "python", "sql", "javascript",
    # Backend & APIs
    "spring", "spring boot", "spring mvc", "spring aop", "hibernate", "jpa",
    "rest api", "restful", "backend",
    # Frontend
    "react",
    # Databases & caching
    "postgresql", "postgres", "mysql", "redis", "rdbms", "dbms", "database",
    # Build / test / tools
    "maven", "junit", "postman", "git", "github",
    # DevOps
    "docker", "docker compose",
    # CS fundamentals — explicitly asked for in most fresher JDs
    "data structures", "algorithms", "dsa", "oop",
    "object oriented", "solid principles", "operating systems", "computer networks",
    # Data analysis (internship + Python/SQL)
    "data analysis", "data cleaning", "data validation", "reporting",
    "joins", "aggregations", "etl", "data",
    # AI project
    "langchain", "openai", "llm", "streamlit",
]

MIN_MATCH_COUNT = 2

# Matched against the FULL JD text — only terms that disqualify a posting
# no matter where they appear.
BLOCKED_KEYWORDS = {
    "unpaid",
    "commission only",
}

# Matched against the TITLE only — these are only a meaningful "wrong job"
# signal when they describe the role itself. Fresher JDs routinely mention
# e.g. "internship experience is a plus" or list PHP/Android among optional
# skills, so scanning the full description for them rejected good postings.
# Seniority words live here too: the candidate is a 2026 graduate, so
# anything titled Senior/Lead/etc. is out regardless of the JD body.
TITLE_ONLY_BLOCKED_KEYWORDS = {
    # Wrong job family
    "sales",
    "marketing",
    "medical",
    "customer support",
    "designer",
    "graphic",
    "teacher",
    "content writer",
    "account executive",
    "php",
    "wordpress",
    "laravel",
    "ios",
    "android",
    "mobile developer",
    "frontend",
    "front end",
    "front-end",
    # Internships — candidate graduated May 2026 and wants full-time roles
    "intern",
    "internship",
    # Seniority
    "senior",
    "sr",
    "lead",
    "principal",
    "staff",
    "architect",
    "manager",
    "head",
    "director",
    "vp",
    "vice president",
    "sse",
    "ii",
    "iii",
    "sde2",
    "sde3",
    "sde-2",
    "sde-3",
}

# Third-party recruiting marketplaces that repost jobs on LinkedIn/Indeed
# under their own name as if THEY were the employer — confirmed live
# against production data: "Hire Feed" and "Hired" postings both read
# "Payout: $X/hour ... We are hiring for [some other company]", Scoutit's
# read "for our client: Bessemer Venture Partners", Talentgigs' are
# templated agency briefs, not a direct company JD. Together ~180 rows
# (5.4%) of the real production DB. Blocked on company name rather than
# any JD-text keyword since the postings' actual content varies (that's
# the marketplace pattern) but the reposting entity's name doesn't.
BLOCKED_COMPANIES = {
    "hire feed",
    "scoutit",
    "hired",
    "talentgigs",
}

# Maximum experience FLOOR a posting may require to be kept — candidate is
# a 2026 graduate targeting 0-1 year roles. A JD whose stated range starts
# above this (e.g. "2-4 years", "3+ years") is rejected; "0-2 years" or
# "1-3 years" is kept since the candidate meets its lower bound. JDs that
# don't state years at all aren't penalized. See pipeline.should_keep().
MAX_EXPERIENCE_YEARS = 1

# Employee-count thresholds + bonus points for the "big company" scoring
# boost in pipeline.compute_confidence(). jobspy reports company size as a
# bucketed string (e.g. "10,000+", "1,001 to 5,000") — parsed via
# pipeline.parse_company_size().
#
# Lowered back down 2026-08 (25/12 -> 10/5, set 2026-07) plus KEYWORD_MATCH_CAP/
# ATS_MATCH_BONUS added below — confirmed live against the real production
# DB (3,311 rows) that the 25/12 company bonus, stacked on top of a +40
# ATS-type bonus that ~83% of ALL postings already receive (detect_ats()
# scores anything not literally unrecognized as "non-generic", so LinkedIn/
# Naukri/Indeed postings get the same +40 as an actual Workday listing),
# was propping up repeat Genpact/PwC postings (10 real keyword matches,
# confidence 0.710) above genuinely stronger-fit postings at companies
# jobspy didn't report a size for (12-15 real keyword matches, confidence
# only 0.472-0.490 purely because company_size came back 0). Simulating
# the new weights across all 3,311 rows: 20 of the current top-40 postings
# by confidence are Genpact/PwC repeats propped up mainly by the company
# bonus and drop out, replaced by 20 postings with materially higher real
# keyword-match counts that were previously buried near 0.47-0.49.
BIG_COMPANY_MIN_EMPLOYEES = 1000
BIG_COMPANY_BONUS = 10
MID_COMPANY_MIN_EMPLOYEES = 200
MID_COMPANY_BONUS = 5

# compute_confidence() previously ran keyword match count through
# resume_scorer.score_resume() (0.6 per match + a placeholder ATS score
# worth up to 40) — that function is shared with dynamic_resume_builder.py's
# actual tailored-RESUME quality scoring (real ATS formatting/structure
# check), a genuinely different concern; reusing it here via a fake
# ats_result was a confusing coincidence, not an intentional shared
# formula, and its 0.6-per-match weighting made keyword fit almost
# irrelevant next to the flat ATS/company bonuses. compute_confidence()
# now has its own formula (see pipeline.py) where keyword match is the
# dominant factor: matches are scaled against KEYWORD_MATCH_CAP (chosen
# from the real distribution — median match count is 6, so 12 represents
# a genuinely strong, not just typical, fit) up to KEYWORD_MATCH_WEIGHT
# points, with the ATS/company-size bonuses reduced to real tiebreakers.
KEYWORD_MATCH_CAP = 12
KEYWORD_MATCH_WEIGHT = 75
ATS_MATCH_BONUS = 15

"""
summary_generator.py

Production ATS Summary Generator
"""

import re
import logging

from groq import Groq

from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
)

logger = logging.getLogger(__name__)

client = None
gemini_client = None

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)

if GEMINI_API_KEY:
    from google import genai
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def _call_groq(prompt: str) -> str:
    if client is None:
        raise RuntimeError("Groq unavailable — no GROQ_API_KEY")
    # gpt-oss is a reasoning model: its hidden reasoning tokens count against
    # the completion budget, so the old 220-token cap (sized for a ~120-word
    # summary from llama-3.3) could leave no room for the answer itself.
    # reasoning_effort="low" keeps that overhead small; passed via
    # extra_body so it works on any groq SDK version.
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.2,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        extra_body={"reasoning_effort": "low"},
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        # Raise so generate_summary() falls through to Gemini instead of
        # writing an empty summary into the resume.
        raise RuntimeError(f"Groq returned an empty completion (finish_reason={response.choices[0].finish_reason})")
    return content


def _call_gemini(prompt: str) -> str:
    if gemini_client is None:
        raise RuntimeError("Gemini unavailable — no GEMINI_API_KEY")
    response = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text.strip()


# Common preambles/wrapping an LLM sometimes adds despite being told
# "return only the summary" — stripped so they never end up verbatim in a
# resume a recruiter reads.
_LLM_PREAMBLE_RE_LIST = [
    r'^(?:sure[,!]?\s+)?here(?:\'s| is)\s+(?:the\s+)?(?:rewritten\s+|revised\s+|updated\s+|tailored\s+)?(?:professional\s+)?summary\s*:?\s*',
    r'^sure[,!]?\s*:?\s*',
]


def _clean_llm_output(text: str) -> str:
    text = text.strip().strip('"').strip("'").strip()
    for pattern in _LLM_PREAMBLE_RE_LIST:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
    return text


# Proper display casing for keywords that are acronyms/proper nouns — used
# only in the static fallback sentence below, so a technology name doesn't
# read as "Aws"/"Sql" if naively title-cased.
_DISPLAY_CASE = {
    "sql": "SQL", "aws": "AWS", "ai": "AI", "llm": "LLM", "rag": "RAG",
    "dbt": "DBT", "etl": "ETL", "elt": "ELT", "rds": "RDS", "bi": "BI",
    "db2": "DB2", "rest api": "REST API", "restful": "RESTful",
    "java": "Java", "javascript": "JavaScript", "spring": "Spring",
    "spring boot": "Spring Boot", "spring mvc": "Spring MVC",
    "spring aop": "Spring AOP", "jpa": "JPA",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mysql": "MySQL",
    "junit": "JUnit", "github": "GitHub", "dsa": "DSA", "oop": "OOP",
    "dbms": "DBMS", "rdbms": "RDBMS", "openai": "OpenAI",
    "langchain": "LangChain", "solid principles": "SOLID principles",
    "docker compose": "Docker Compose",
}


def _display_keyword(kw: str) -> str:
    return _DISPLAY_CASE.get(kw, kw[:1].upper() + kw[1:] if kw else kw)


def generate_summary(
    profile,
    job,
    keywords=None,
):

    keywords = keywords or []

    description = ""

    if isinstance(job, dict):
        description = job.get(
            "description",
            ""
        )
    else:
        description = str(job)

    current_summary = profile.get(
        "summary",
        ""
    )

    skills = profile.get(
        "skills",
        ""
    )

    experience = profile.get(
        "experience",
        ""
    )

    keyword_text = ", ".join(
        keywords[:20]
    )

    prompt = f"""
You are an expert resume writer.

Your task is NOT to invent new experience.

Rewrite ONLY the Professional Summary.

Current Summary

{current_summary}

Candidate Experience

{experience}

Technical Skills

{skills}

Target Job Description

{description}

Important ATS Keywords

{keyword_text}

Rules

1. 90-120 words.
2. Professional tone.
3. ATS optimized.
4. Mention only technologies already present in the candidate profile.
5. Naturally include the important keywords.
6. Do NOT exaggerate.
7. Do NOT mention years of experience unless already known.
8. Return only the summary.
"""

    # Returns (summary_text, source, llm_errors) — source/llm_errors let
    # callers (cloud_run.py) surface which path actually served each job,
    # and why, as a GitHub Actions annotation. A silent Groq/Gemini failure
    # here previously had no visible signal outside of logger.warning
    # (invisible without log access, which 403s without admin/write auth
    # on this repo) — confirmed live 2026-08-01: both APIs were failing
    # for 15/15 tailored resumes with no visible error text anywhere.
    llm_errors = {}
    try:
        return _clean_llm_output(_call_groq(prompt)), "groq", llm_errors
    except Exception as e:
        llm_errors["groq"] = str(e)
        logger.warning("Groq summary generation failed, falling back to Gemini: %s", e)

    try:
        return _clean_llm_output(_call_gemini(prompt)), "gemini", llm_errors
    except Exception as e:
        llm_errors["gemini"] = str(e)
        logger.warning("Gemini summary generation failed, using static fallback: %s", e)

    return _static_fallback_summary(keywords), "fallback", llm_errors


def _static_fallback_summary(keywords) -> str:
    # Only reached when BOTH Groq and Gemini fail. The previous version
    # returned byte-identical prose across every JD except for one raw,
    # lowercase, comma-separated keyword clause bolted onto the end (e.g.
    # "...with expertise in python, sql, analytics, rds, ai, tableau, a/b
    # testing.") — an obvious "auto-generated" tell to any recruiter
    # comparing two of the candidate's applications, and ungrammatical
    # next to the properly capitalized prose around it. Weaves 2-3 real
    # keywords into an actual sentence instead, with correct display
    # casing for acronyms (via _display_keyword) rather than a bare dump.
    top = [_display_keyword(k) for k in keywords[:3]]
    if len(top) >= 2:
        keyword_clause = ", ".join(top[:-1]) + f", and {top[-1]}"
    elif top:
        keyword_clause = top[0]
    else:
        keyword_clause = None

    summary = (
        "Backend Developer and Computer Science graduate experienced in "
        "building fault-tolerant services and RESTful APIs using Java, Spring "
        "Boot, PostgreSQL, and Redis, including an idempotent payment engine "
        "that prevents duplicate transactions. Data analysis internship "
        "experience writing Python and SQL scripts to clean, validate, and "
        "report on operational data. Strong foundation in data structures, "
        "OOP, SOLID principles, and DBMS. Available to join immediately."
    )
    if keyword_clause:
        summary += f" Hands-on experience with {keyword_clause} in particular."
    return summary
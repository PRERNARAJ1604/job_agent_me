"""
profile_loader.py
"""

from config import DEFAULT_ANSWERS


def load_profile():
    return {
        "full_name":
            DEFAULT_ANSWERS["full_name"],

        "email":
            DEFAULT_ANSWERS["email"],

        "phone":
            DEFAULT_ANSWERS["phone"],

        "education":
            """
B.Tech, Computer Science
Greater Noida Institute of Technology (2022 - 2026)
            """,

        "experience":
            """
Data Analyst Intern - SkillEn (Aug 2025 - Jan 2026)

• Built Python and SQL scripts to clean and validate operational data
• Wrote optimized MySQL queries for internal reporting
• Built an idempotent payment engine (Java, Spring Boot, Redis, PostgreSQL)
• Built an AI document analysis service (Python, LangChain, OpenAI)
            """,
    }
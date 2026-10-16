"""
role_classifier.py
"""


def classify_role(job_text):

    text = job_text.lower()

    ai_words = [
        "llm",
        "langchain",
        "openai",
        "genai",
        "generative ai",
    ]

    analytics_words = [
        "data analyst",
        "data analysis",
        "dashboard",
        "reporting",
        "excel",
        "power bi",
        "tableau",
    ]

    if any(k in text for k in ai_words):
        return "genai"

    if any(k in text for k in analytics_words):
        return "analytics"

    return "backend"

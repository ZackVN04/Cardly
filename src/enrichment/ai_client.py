import json
import logging
import re

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    "/models/gemini-1.5-flash:generateContent"
)


def mock_enrich(contact_id: str) -> dict:
    return {
        "brief": (
            "A technology professional with extensive experience in software development "
            "and business leadership. Known for building high-performance teams."
        ),
        "keywords": ["software engineering", "technology", "leadership"],
        "highlights": [
            "Experienced technology professional",
            "Strong background in software development",
        ],
        "linkedin_data": None,
        "facebook_data": None,
        "website_data": None,
    }


def _extract_meta(html: str, attr: str, value: str) -> str | None:
    pattern = (
        rf'<meta\s+(?:[^>]*?\s+)?{attr}="{re.escape(value)}"[^>]*?\s+content="([^"]*)"'
        rf'|<meta\s+(?:[^>]*?\s+)?content="([^"]*)"[^>]*?\s+{attr}="{re.escape(value)}"'
    )
    match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return (match.group(1) or match.group(2) or "").strip() or None


async def fetch_linkedin_data(linkedin_url: str) -> dict | None:
    if not linkedin_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(linkedin_url, headers=_BROWSER_HEADERS)
        if resp.status_code != 200:
            return None
        html = resp.text
        title = _extract_meta(html, "property", "og:title")
        description = _extract_meta(html, "property", "og:description") or _extract_meta(
            html, "name", "description"
        )
        if not title and not description:
            return None
        return {
            "connections": None,
            "current_role": title,
            "education": [],
            "recent_posts": [description] if description else [],
        }
    except Exception as exc:
        logger.debug("LinkedIn fetch failed for %s: %s", linkedin_url, exc)
        return None


async def fetch_website_data(website_url: str) -> dict | None:
    if not website_url:
        return None
    if not website_url.startswith(("http://", "https://")):
        website_url = f"https://{website_url}"
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(website_url, headers=_BROWSER_HEADERS)
        if resp.status_code != 200:
            return None
        html = resp.text
        about = _extract_meta(html, "property", "og:description") or _extract_meta(
            html, "name", "description"
        )
        if not about:
            return None
        return {
            "about": about,
            "founded": None,
            "team_size": None,
        }
    except Exception as exc:
        logger.debug("Website fetch failed for %s: %s", website_url, exc)
        return None


async def fetch_facebook_data(facebook_url: str) -> dict | None:
    if not facebook_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(facebook_url, headers=_BROWSER_HEADERS)
        if resp.status_code != 200:
            return None
        html = resp.text
        description = _extract_meta(html, "property", "og:description")
        if not description:
            return None
        return {
            "profile_url": facebook_url,
            "followers": None,
            "recent_posts": [description],
        }
    except Exception as exc:
        logger.debug("Facebook fetch failed for %s: %s", facebook_url, exc)
        return None


async def call_gemini(contact_data: dict, social_data: dict) -> dict:
    prompt = _build_prompt(contact_data, social_data)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3,
        },
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            _GEMINI_URL,
            params={"key": settings.GEMINI_API_KEY},
            json=payload,
        )
        resp.raise_for_status()
    return parse_enrichment_result(resp.json())


def _build_prompt(contact_data: dict, social_data: dict) -> str:
    lines = [
        "You are a professional contact enrichment assistant.",
        "Generate a concise profile summary based on the information below.",
        "",
        "Contact:",
        f"  Name: {contact_data.get('full_name') or 'Unknown'}",
        f"  Position: {contact_data.get('position') or 'N/A'}",
        f"  Company: {contact_data.get('company') or 'N/A'}",
        f"  Email: {contact_data.get('email') or 'N/A'}",
        f"  Website: {contact_data.get('website') or 'N/A'}",
        f"  LinkedIn: {contact_data.get('linkedin_url') or 'N/A'}",
    ]

    linkedin = social_data.get("linkedin_data")
    if linkedin:
        lines += [
            "",
            "LinkedIn (public):",
            f"  Role: {linkedin.get('current_role') or 'N/A'}",
        ]
        if linkedin.get("recent_posts"):
            lines.append(f"  Bio: {linkedin['recent_posts'][0]}")

    website = social_data.get("website_data")
    if website and website.get("about"):
        lines += ["", f"Website about: {website['about']}"]

    facebook = social_data.get("facebook_data")
    if facebook and facebook.get("recent_posts"):
        lines += ["", f"Facebook bio: {facebook['recent_posts'][0]}"]

    lines += [
        "",
        'Return JSON only — no markdown, no explanation:',
        '{',
        '  "brief": "2-4 sentence professional summary",',
        '  "keywords": ["3-6 industry or skill keywords"],',
        '  "highlights": ["2-4 notable facts or achievements"]',
        '}',
    ]
    return "\n".join(lines)


def parse_enrichment_result(gemini_response: dict) -> dict:
    candidates = gemini_response.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini returned no candidates")
    text = candidates[0]["content"]["parts"][0]["text"].strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    return {
        "brief": str(parsed.get("brief", "")),
        "keywords": [str(k) for k in parsed.get("keywords", [])],
        "highlights": [str(h) for h in parsed.get("highlights", [])],
    }

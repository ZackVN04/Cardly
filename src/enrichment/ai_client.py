def mock_enrich(contact_id: str) -> dict:
    """Mock enrichment data cho ENVIRONMENT='test' — không gọi Gemini thật."""
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


# ---------------------------------------------------------------------------
# W7: implement các hàm dưới đây với Gemini pipeline thật
# ---------------------------------------------------------------------------

async def fetch_linkedin_data(linkedin_url: str) -> dict | None:
    # W7: scrape public LinkedIn, return {connections, current_role, education, recent_posts}
    return None


async def fetch_website_data(website_url: str) -> dict | None:
    # W7: scrape website, extract about/founded/team_size
    return None


async def fetch_facebook_data(facebook_url: str) -> dict | None:
    # W7: scrape public Facebook, return {profile_url, followers, recent_posts}
    return None


async def call_gemini(contact_data: dict, social_data: dict) -> dict:
    # W7: build prompt + call Gemini API → return {brief, keywords, highlights}
    raise NotImplementedError("W7: Gemini pipeline not yet implemented")


def parse_enrichment_result(gemini_response: dict) -> dict:
    # W7: parse JSON response từ Gemini
    raise NotImplementedError("W7: Gemini response parser not yet implemented")

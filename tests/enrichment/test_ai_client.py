import pytest

from src.enrichment.ai_client import (
    EnrichmentAIError,
    fetch_website_data,
    parse_enrichment_result,
)


def _gemini_response(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_parse_enrichment_result_accepts_fenced_json():
    result = parse_enrichment_result(_gemini_response("""
```json
{
  "brief": "Senior AI builder.",
  "keywords": ["AI", "backend", "automation"],
  "highlights": ["Built production AI systems"]
}
```
"""))

    assert result["brief"] == "Senior AI builder."
    assert result["keywords"] == ["AI", "backend", "automation"]
    assert result["highlights"] == ["Built production AI systems"]


def test_parse_enrichment_result_rejects_invalid_json():
    with pytest.raises(EnrichmentAIError):
        parse_enrichment_result(_gemini_response("not json"))


async def test_fetch_website_data_normalizes_url_and_reads_meta(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        encoding = "utf-8"
        content = (
            b'<html><meta name="description" content="AI software company"></html>'
        )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers):
            captured["url"] = url
            return FakeResponse()

    monkeypatch.setattr("src.enrichment.ai_client.httpx.AsyncClient", FakeClient)

    result = await fetch_website_data("example.com")

    assert captured["url"] == "https://example.com"
    assert result["about"] == "AI software company"

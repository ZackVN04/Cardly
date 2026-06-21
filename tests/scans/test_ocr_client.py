from unittest.mock import AsyncMock

import pytest

from src.scans.ocr_client import extract_card_data, parse_ocr_response


def test_parse_ocr_response_extracts_embedded_json():
    raw = """
Here is the extracted data:
{
  "full_name": "Nguyen Van A",
  "phone": "0901234567",
  "email": "a@cardly.dev",
  "ignored": "not allowed"
}
"""

    result = parse_ocr_response(raw)

    assert result["full_name"] == "Nguyen Van A"
    assert result["phone"] == ["0901234567"]
    assert result["email"] == "a@cardly.dev"
    assert "ignored" not in result


async def test_extract_card_data_rejects_empty_ocr_result(monkeypatch):
    monkeypatch.setattr(
        "src.scans.ocr_client._fetch_image",
        AsyncMock(return_value=(b"image", "image/jpeg")),
    )
    monkeypatch.setattr(
        "src.scans.ocr_client._call_gemini_with_retry",
        AsyncMock(return_value="{}"),
    )

    with pytest.raises(ValueError, match="no usable contact fields"):
        await extract_card_data("https://example.com/card.jpg")

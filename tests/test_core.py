"""
W3 unit tests — core/ + models.py
Tests cover: PyObjectId, BaseDocument, security, pagination, rate_limit
No external dependencies required (no DB, no network).
"""
from datetime import datetime

import pytest
from bson import ObjectId
from pydantic import BaseModel

from src.core.pagination import PaginatedResponse, paginate_query
from src.core.rate_limit import limiter
from src.core.security import hash_password, verify_password
from src.models import BaseDocument, PyObjectId


# ---------------------------------------------------------------------------
# PyObjectId
# ---------------------------------------------------------------------------


def test_pyobjectid_accepts_valid_string():
    oid = str(ObjectId())
    assert PyObjectId.validate(oid) == oid


def test_pyobjectid_accepts_bson_objectid():
    oid = ObjectId()
    result = PyObjectId.validate(oid)
    assert result == str(oid)
    assert isinstance(result, str)


def test_pyobjectid_rejects_invalid_string():
    with pytest.raises(ValueError):
        PyObjectId.validate("not-an-objectid")


def test_pyobjectid_rejects_empty_string():
    with pytest.raises(ValueError):
        PyObjectId.validate("")


def test_pyobjectid_works_in_pydantic_model():
    class Doc(BaseModel):
        id: PyObjectId

    oid = str(ObjectId())
    doc = Doc(id=oid)
    assert doc.id == oid


def test_pyobjectid_coerces_bson_in_pydantic_model():
    class Doc(BaseModel):
        id: PyObjectId

    oid = ObjectId()
    doc = Doc(id=oid)
    assert doc.id == str(oid)


# ---------------------------------------------------------------------------
# BaseDocument
# ---------------------------------------------------------------------------


def test_base_document_id_defaults_to_none():
    doc = BaseDocument()
    assert doc.id is None


def test_base_document_auto_sets_created_at():
    doc = BaseDocument()
    assert isinstance(doc.created_at, datetime)


def test_base_document_auto_sets_updated_at():
    doc = BaseDocument()
    assert isinstance(doc.updated_at, datetime)


def test_base_document_accepts_id_via_alias():
    oid = str(ObjectId())
    doc = BaseDocument(**{"_id": oid})
    assert doc.id == oid


def test_base_document_accepts_id_via_field_name():
    oid = str(ObjectId())
    doc = BaseDocument(id=oid)
    assert doc.id == oid


def test_base_document_timestamps_are_recent():
    before = datetime.utcnow()
    doc = BaseDocument()
    after = datetime.utcnow()
    # created_at should be between before and after (UTC, ignoring timezone info)
    assert doc.created_at.replace(tzinfo=None) >= before
    assert doc.created_at.replace(tzinfo=None) <= after


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


def test_hash_password_not_plaintext():
    hashed = hash_password("supersecret")
    assert hashed != "supersecret"


def test_hash_password_starts_with_bcrypt_prefix():
    hashed = hash_password("supersecret")
    assert hashed.startswith("$2b$")


def test_hash_password_rounds_12():
    hashed = hash_password("supersecret")
    # bcrypt format: $2b$<rounds>$...
    rounds = int(hashed.split("$")[2])
    assert rounds == 12


def test_hash_password_unique_salts():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2


def test_verify_password_correct():
    hashed = hash_password("correct_password")
    assert verify_password("correct_password", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("correct_password")
    assert verify_password("wrong_password", hashed) is False


def test_verify_password_empty_wrong():
    hashed = hash_password("correct_password")
    assert verify_password("", hashed) is False


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def test_paginate_query_page1_limit10():
    skip, limit = paginate_query(page=1, limit=10)
    assert skip == 0
    assert limit == 10


def test_paginate_query_page2_limit10():
    skip, limit = paginate_query(page=2, limit=10)
    assert skip == 10
    assert limit == 10


def test_paginate_query_page3_limit5():
    skip, limit = paginate_query(page=3, limit=5)
    assert skip == 10
    assert limit == 5


def test_paginate_query_page1_limit1():
    skip, limit = paginate_query(page=1, limit=1)
    assert skip == 0
    assert limit == 1


def test_paginated_response_fields():
    class Item(BaseModel):
        name: str

    response = PaginatedResponse[Item](
        items=[Item(name="a"), Item(name="b")],
        total=50,
        skip=10,
        limit=10,
        pages=5,
    )
    assert len(response.items) == 2
    assert response.total == 50
    assert response.skip == 10
    assert response.limit == 10
    assert response.pages == 5


def test_paginated_response_empty():
    class Item(BaseModel):
        value: int

    response = PaginatedResponse[Item](
        items=[],
        total=0,
        skip=0,
        limit=10,
        pages=0,
    )
    assert response.items == []
    assert response.total == 0


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


def test_limiter_instance_exists():
    assert limiter is not None


def test_limiter_has_key_func():
    assert limiter._key_func is not None

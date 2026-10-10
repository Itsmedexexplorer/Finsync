"""Unit tests for EntityNormalizer in VERITY."""

import pytest
from backend.entity_resolution.normalizer import EntityNormalizer


def test_normalize_name_titles_and_honorifics() -> None:
    # Leading honorifics
    assert EntityNormalizer.normalize_name("M/s. Ramesh Traders") == "ramesh traders"
    assert EntityNormalizer.normalize_name("Dr. Anil Kumar") == "anil kumar"
    assert EntityNormalizer.normalize_name("Shri Rajesh Gupta") == "rajesh gupta"

    # Trailing honorifics
    assert EntityNormalizer.normalize_name("Rahul bhai") == "rahul"
    assert EntityNormalizer.normalize_name("Sharma ji") == "sharma"

    # Punctuation and hyphens
    assert EntityNormalizer.normalize_name("Rahul-Kumar") == "rahul kumar"
    assert EntityNormalizer.normalize_name("  Shree   Electronics   Pvt   Ltd  ") == "shree electronics pvt ltd"


def test_extract_core_name_tokens() -> None:
    tokens = EntityNormalizer.extract_core_name_tokens("Shree Electronics Pvt Ltd")
    assert "pvt" not in tokens
    assert "ltd" not in tokens
    assert "electronics" in tokens
    assert "shree" not in tokens or "electronics" in tokens


def test_normalize_phone_indian_formats() -> None:
    expected = "9876543210"
    
    # 10-digit plain
    assert EntityNormalizer.normalize_phone("9876543210") == expected
    # Formatted with spaces / dashes
    assert EntityNormalizer.normalize_phone("98765-43210") == expected
    assert EntityNormalizer.normalize_phone("+91 98765 43210") == expected
    assert EntityNormalizer.normalize_phone("+91-9876543210") == expected
    # 12-digit with 91 prefix
    assert EntityNormalizer.normalize_phone("919876543210") == expected
    # 11-digit with 0 prefix
    assert EntityNormalizer.normalize_phone("09876543210") == expected

    # Invalid / too short
    assert EntityNormalizer.normalize_phone("12345") is None
    assert EntityNormalizer.normalize_phone("") is None


def test_normalize_upi_vpa() -> None:
    assert EntityNormalizer.normalize_upi_vpa("rahulkumar@ybl") == "rahulkumar@ybl"
    assert EntityNormalizer.normalize_upi_vpa("  RAHUL.KUMAR@OKHDFCBANK  ") == "rahul.kumar@okhdfcbank"
    assert EntityNormalizer.normalize_upi_vpa("invalidvpa") is None
    assert EntityNormalizer.normalize_upi_vpa("") is None


def test_normalize_tax_id() -> None:
    # GSTIN (15 chars)
    assert EntityNormalizer.normalize_tax_id("29abcde1234f1z5") == "29ABCDE1234F1Z5"
    assert EntityNormalizer.normalize_tax_id(" 29-ABCDE-1234F-1Z5 ") == "29ABCDE1234F1Z5"
    
    # PAN (10 chars)
    assert EntityNormalizer.normalize_tax_id("abcde1234f") == "ABCDE1234F"


def test_is_initials_match() -> None:
    assert EntityNormalizer.is_initials_match("R. Kumar", "Rahul Kumar") is True
    assert EntityNormalizer.is_initials_match("Rahul Kumar", "R Kumar") is True
    assert EntityNormalizer.is_initials_match("P. Sharma", "Pooja Sharma") is True
    assert EntityNormalizer.is_initials_match("Rahul Kumar", "Rohit Kumar") is False
    assert EntityNormalizer.is_initials_match("R. Sharma", "Rahul Kumar") is False

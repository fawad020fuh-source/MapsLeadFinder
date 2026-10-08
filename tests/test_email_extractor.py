from src.email_extractor import EmailExtractor


def test_normalizes_simple_obfuscation():
    extractor = EmailExtractor()
    assert extractor._normalize_email("hello[at]example.com") == "hello@example.com"
    assert extractor._normalize_email("hello [dot] example [dot] com") == "hello.example.com"


def test_filters_junk_and_keeps_business_email():
    extractor = EmailExtractor()
    assert extractor._is_junk("noreply@example.com") is True
    assert extractor._is_junk("example@example.com") is True
    assert extractor._is_junk("hello@valid-domain.com") is False


def test_extract_standard_email_from_text():
    extractor = EmailExtractor()
    text = "Call us at support@acme.com or hello [at] acme [dot] com"
    result = extractor._collect_standard_matches(text)
    assert "support@acme.com" in result or "hello@acme.com" in result


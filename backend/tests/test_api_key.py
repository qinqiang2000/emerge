from app.services.api_key import generate_api_key, parse_prefix, verify_api_key


def test_generate_format():
    key, prefix, hashed = generate_api_key()
    assert key.startswith(f"ek_{prefix}-")
    assert len(prefix) == 8
    assert len(key.split("-", 1)[1]) == 32
    assert hashed != key


def test_verify_round_trip():
    key, prefix, hashed = generate_api_key()
    assert verify_api_key(key, prefix=prefix, key_hash=hashed) is True
    assert verify_api_key(key + "x", prefix=prefix, key_hash=hashed) is False


def test_verify_wrong_prefix():
    key, _, hashed = generate_api_key()
    assert verify_api_key(key, prefix="WRONGPRE", key_hash=hashed) is False


def test_verify_malformed_keys_return_false():
    _, prefix, hashed = generate_api_key()
    for bad in ("", "ek_no-dash", "no-prefix-thing", "ek_-onlysecret"):
        assert verify_api_key(bad, prefix=prefix, key_hash=hashed) is False


def test_parse_prefix():
    assert parse_prefix("ek_ABCD1234-secret") == "ABCD1234"
    assert parse_prefix("notakey") is None
    assert parse_prefix("ek_-emptyprefix") is None

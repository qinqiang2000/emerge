from datetime import timedelta

import pytest

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.errors import EmergeError


def test_hash_password_round_trip():
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False


def test_hash_password_is_random():
    assert hash_password("same") != hash_password("same")


def test_jwt_round_trip():
    token = create_access_token(subject="42")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"


def test_jwt_expired_raises():
    token = create_access_token(subject="1", expires_delta=timedelta(seconds=-1))
    with pytest.raises(EmergeError):
        decode_access_token(token)


def test_jwt_tampered_raises():
    token = create_access_token(subject="1") + "garbage"
    with pytest.raises(EmergeError):
        decode_access_token(token)

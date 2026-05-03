from app.core.security import hash_password, verify_password


def test_hash_password_round_trip():
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h) is True
    assert verify_password("wrong", h) is False


def test_hash_password_is_random():
    assert hash_password("same") != hash_password("same")

import secrets

import bcrypt


_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _gen_token(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix, hash). Caller persists prefix + hash; full_key
    is shown to the user only once and is never recoverable."""
    prefix = _gen_token(8)
    secret = _gen_token(32)
    full = f"ek_{prefix}-{secret}"
    hashed = bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return full, prefix, hashed


def parse_prefix(presented: str) -> str | None:
    if not presented.startswith("ek_") or "-" not in presented:
        return None
    pres_prefix, _ = presented.removeprefix("ek_").split("-", 1)
    return pres_prefix or None


def verify_api_key(presented: str, *, prefix: str, key_hash: str) -> bool:
    if not presented.startswith("ek_") or "-" not in presented:
        return False
    pres_prefix, pres_secret = presented.removeprefix("ek_").split("-", 1)
    if not secrets.compare_digest(pres_prefix.encode(), prefix.encode()):
        return False
    try:
        return bcrypt.checkpw(pres_secret.encode("utf-8"), key_hash.encode("utf-8"))
    except (ValueError, KeyError):
        return False

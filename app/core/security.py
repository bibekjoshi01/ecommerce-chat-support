from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 260_000
PASSWORD_SALT_SIZE = 16
TOKEN_VERSION = 1


@dataclass(frozen=True, slots=True)
class AgentSessionClaims:
    user_id: UUID
    agent_id: UUID
    expires_at: datetime


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padded = raw + ("=" * (-len(raw) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")

    salt = secrets.token_bytes(PASSWORD_SALT_SIZE)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return (
        f"{PBKDF2_ALGORITHM}$"
        f"{PBKDF2_ITERATIONS}$"
        f"{_b64url_encode(salt)}$"
        f"{_b64url_encode(digest)}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = stored_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != PBKDF2_ALGORITHM:
        return False

    try:
        iterations = int(raw_iterations)
        salt = _b64url_decode(raw_salt)
        expected_digest = _b64url_decode(raw_digest)
    except (ValueError, TypeError):
        return False

    candidate_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(candidate_digest, expected_digest)


def create_agent_access_token(
    *,
    user_id: UUID,
    agent_id: UUID,
    secret: str,
    ttl_minutes: int,
) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=ttl_minutes)
    payload = {
        "v": TOKEN_VERSION,
        "uid": str(user_id),
        "aid": str(agent_id),
        "exp": int(expires_at.timestamp()),
        "iat": int(now.timestamp()),
    }

    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    payload_segment = _b64url_encode(payload_raw)
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_segment.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    token = f"{payload_segment}.{_b64url_encode(signature)}"
    return token, expires_at


def decode_agent_access_token(token: str, secret: str) -> AgentSessionClaims:
    try:
        payload_segment, signature_segment = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Malformed token") from exc

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload_segment.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    try:
        actual_signature = _b64url_decode(signature_segment)
    except (ValueError, TypeError) as exc:
        raise ValueError("Malformed token signature") from exc

    if not hmac.compare_digest(expected_signature, actual_signature):
        raise ValueError("Invalid token signature")

    try:
        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed token payload") from exc

    if not isinstance(payload, dict):
        raise ValueError("Malformed token payload")
    if payload.get("v") != TOKEN_VERSION:
        raise ValueError("Unsupported token version")

    try:
        user_id = UUID(str(payload["uid"]))
        agent_id = UUID(str(payload["aid"]))
        expires_at = datetime.fromtimestamp(int(payload["exp"]), UTC)
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("Malformed token payload") from exc

    if expires_at <= datetime.now(UTC):
        raise ValueError("Token expired")

    return AgentSessionClaims(
        user_id=user_id,
        agent_id=agent_id,
        expires_at=expires_at,
    )

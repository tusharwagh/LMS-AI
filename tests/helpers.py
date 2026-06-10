"""Shared test helpers."""

from __future__ import annotations

import uuid


def unique_tag(prefix: str = "") -> str:
    tag = uuid.uuid4().hex[:8]
    return f"{prefix}{tag}" if prefix else tag

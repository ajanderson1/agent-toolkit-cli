"""Tiny output helper — header before main output, summary after.

Both write to stderr so stdout stays machine-readable. Honours
``AGENT_TOOLKIT_QUIET=1`` so tests and pipes can suppress chrome.
"""
from __future__ import annotations

import os
import sys


def _quiet() -> bool:
    return os.environ.get("AGENT_TOOLKIT_QUIET") == "1"


def header(message: str) -> None:
    if _quiet():
        return
    print(message, file=sys.stderr)


def summary(message: str) -> None:
    if _quiet():
        return
    print(message, file=sys.stderr)

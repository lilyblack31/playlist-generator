#!/usr/bin/env python3
"""
Simple ANSI color helpers for pretty terminal output.
Works in most terminals (including macOS Terminal and iTerm).
"""

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

FG_RED = "\033[31m"
FG_GREEN = "\033[32m"
FG_YELLOW = "\033[33m"
FG_BLUE = "\033[34m"
FG_MAGENTA = "\033[35m"
FG_CYAN = "\033[36m"
FG_WHITE = "\033[37m"
FG_GRAY = "\033[90m"


def color(text: str, *effects: str) -> str:
    """
    Wrap text in one or more color/effect codes.

    Example:
        print(color("Hello", FG_GREEN, BOLD))
    """
    return "".join(effects) + text + RESET

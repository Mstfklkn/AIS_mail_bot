"""Terminal arayüzü stilleri."""

import os
import sys

# ANSI renk kodları
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"

# Renk desteği (NO_COLOR veya pipe'da kapalı)
NO_COLOR = os.environ.get("NO_COLOR") is not None
SUPPORTS_COLOR = sys.stdout.isatty() and not NO_COLOR


def _c(code: str, text: str) -> str:
    """Renk uygula (destek yoksa düz metin)."""
    return f"{code}{text}{RESET}" if SUPPORTS_COLOR else text


def title(t: str) -> str:
    return _c(BOLD + CYAN, t)


def success(t: str) -> str:
    return _c(GREEN, t)


def error(t: str) -> str:
    return _c(RED, t)


def warn(t: str) -> str:
    return _c(YELLOW, t)


def dim(t: str) -> str:
    return _c(DIM, t)


def accent(t: str) -> str:
    return _c(MAGENTA, t)


def box(lines: list[str], width: int = 50) -> str:
    """Kutulu metin oluştur."""
    top = "╭" + "─" * (width - 2) + "╮"
    bottom = "╰" + "─" * (width - 2) + "╯"
    result = [top]
    for line in lines:
        padding = width - 4 - len(line)
        result.append("│  " + line + " " * max(0, padding) + "  │")
    result.append(bottom)
    return "\n".join(result)


def banner() -> str:
    """Başlık banner'ı."""
    lines = [
        "",
        _c(BOLD + CYAN, "  ╭─────────────────────────────╮"),
        _c(BOLD + CYAN, "  │") + _c(WHITE, "     📧 Mail Bot") + _c(BOLD + CYAN, "                 │"),
        _c(BOLD + CYAN, "  ╰─────────────────────────────╯"),
        "",
    ]
    return "\n".join(lines)


def separator(char: str = "─", length: int = 40) -> str:
    return dim(char * length)


def progress_bar(current: int, total: int, width: int = 20) -> str:
    """İlerleme çubuğu."""
    if total == 0:
        return "[" + " " * width + "]"
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {current}/{total}"

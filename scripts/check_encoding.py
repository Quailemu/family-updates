import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INCLUDE_ROOTS = [
    ROOT / "app.py",
    ROOT / "config.py",
    ROOT / "README.md",
    ROOT / "docs",
    ROOT / "supabase",
    ROOT / "pages",
]

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__"}
SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".mp4",
    ".mov",
    ".pdf",
    ".zip",
}

# Typical mojibake fragments, defined via escapes to avoid source-encoding drift.
PATTERN_REGEXES = [
    r"\u00e2\u20ac[\u0080-\u00ff]",  # â€…
    r"\u00e2\u2020[\u0080-\u00ff]",  # â†…
    r"\u00c3[\u0080-\u00bf]",        # Ã...
    r"\u00c2[\u0080-\u00bf]",        # Â...
    r"\ufffd",                       # replacement char �
]
REGEX = re.compile("|".join(PATTERN_REGEXES))


def iter_files():
    for target in INCLUDE_ROOTS:
        if not target.exists():
            continue
        if target.is_file():
            yield target
            continue
        for path in target.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() in SKIP_SUFFIXES:
                continue
            yield path


def main() -> int:
    findings = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if REGEX.search(line):
                findings.append((path.relative_to(ROOT), lineno, line.strip()))

    if findings:
        print("Encoding check failed. Possible mojibake found:")
        for rel, lineno, line in findings:
            print(f"{rel}:{lineno}: {line}")
        return 1

    print("Encoding check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


import argparse
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

# Conservative mapping for common mojibake sequences.
REPLACEMENTS = [
    ("\u00e2\u20ac\u201c", "-"),   # â€“
    ("\u00e2\u20ac\u201d", "-"),   # â€”
    ("\u00e2\u20ac\u00a2", "- "),  # â€¢
    ("\u00e2\u2020\u2019", "->"),  # â†’
    ("\u00e2\u2020\u0090", "<-"),  # â†
    ("\u00e2\u20ac\u0153", '"'),    # â€œ
    ("\u00e2\u20ac\u009d", '"'),    # â€
    ("\u00e2\u20ac\u02dc", "'"),    # â€˜
    ("\u00e2\u20ac\u2122", "'"),    # â€™
    ("\u00c2\u00a3", "£"),          # Â£
]


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


def normalize_text(text: str) -> str:
    output = text
    for bad, good in REPLACEMENTS:
        output = output.replace(bad, good)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize common mojibake text patterns.")
    parser.add_argument("--write", action="store_true", help="Write fixes to files.")
    parser.add_argument("--check", action="store_true", help="Only report files that need changes.")
    args = parser.parse_args()

    # Default to check mode for safety.
    write_mode = bool(args.write)
    check_mode = bool(args.check or not write_mode)

    changed_files: list[Path] = []
    for path in iter_files():
        try:
            original = path.read_text(encoding="utf-8")
        except Exception:
            continue
        normalized = normalize_text(original)
        if normalized == original:
            continue
        changed_files.append(path)
        if write_mode:
            path.write_text(normalized, encoding="utf-8")

    if changed_files:
        print("Text normalization detected files with common mojibake patterns:")
        for path in changed_files:
            print(path.relative_to(ROOT))
        if check_mode:
            print("Run: python scripts/normalize_text.py --write")
            return 1

    if write_mode:
        print("Normalization complete.")
    else:
        print("No normalization changes needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


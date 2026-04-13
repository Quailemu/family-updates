import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRANSCRIPT_DIR = ROOT / "docs" / "walkthrough-transcripts"

PATTERN_REGEXES = [
    r"\u00e2\u20ac[\u0080-\u00ff]",  # â€…
    r"\u00e2\u2020[\u0080-\u00ff]",  # â†…
    r"\u00c3[\u0080-\u00bf]",        # Ã...
    r"\u00c2[\u0080-\u00bf]",        # Â...
    r"\ufffd",                       # replacement char �
]
BAD_REGEX = re.compile("|".join(PATTERN_REGEXES))

REPLACEMENTS = [
    ("\u00e2\u20ac\u201c", "-"),   # â€“
    ("\u00e2\u20ac\u201d", "-"),   # â€”
    ("\u00e2\u20ac\u00a2", "- "),  # â€¢
    ("\u00e2\u2020\u2019", "->"),  # â†’
    ("\u00e2\u2020\u0090", "<-"),  # â†
    ("\u00e2\u20ac\u0153", '"'),   # â€œ
    ("\u00e2\u20ac\u009d", '"'),   # â€
    ("\u00e2\u20ac\u02dc", "'"),   # â€˜
    ("\u00e2\u20ac\u2122", "'"),   # â€™
    ("\u00c2\u00a3", "\u00a3"),    # Â£ -> £
]


def safe_print(text: str) -> None:
    stream = sys.stdout
    encoding = stream.encoding or "utf-8"
    data = (str(text) + "\n").encode(encoding, errors="backslashreplace")
    stream.buffer.write(data)


def normalize_text(text: str) -> str:
    output = text
    for bad, good in REPLACEMENTS:
        output = output.replace(bad, good)
    return output


def resolve_targets(raw_paths: list[str]) -> list[Path]:
    targets: list[Path] = []
    if raw_paths:
        for p in raw_paths:
            path = Path(p)
            if not path.is_absolute():
                path = (ROOT / path).resolve()
            if path.exists() and path.is_file() and path.suffix.lower() == ".md":
                targets.append(path)
        return targets

    if not DEFAULT_TRANSCRIPT_DIR.exists():
        return targets
    return sorted(p for p in DEFAULT_TRANSCRIPT_DIR.rglob("*.md") if p.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description="Check/fix mojibake in walkthrough transcripts.")
    parser.add_argument("--check", action="store_true", help="Report issues and return non-zero if found.")
    parser.add_argument("--write", action="store_true", help="Apply known fixes in place.")
    parser.add_argument("paths", nargs="*", help="Optional transcript file paths.")
    args = parser.parse_args()

    write_mode = bool(args.write)
    check_mode = bool(args.check or not write_mode)

    targets = resolve_targets(args.paths)
    if not targets:
        safe_print("Transcript guard: no target markdown files found.")
        return 0

    findings: list[tuple[Path, int, str]] = []
    changed_files: list[Path] = []

    for path in targets:
        try:
            original = path.read_text(encoding="utf-8")
        except Exception:
            continue
        normalized = normalize_text(original)
        if write_mode and normalized != original:
            path.write_text(normalized, encoding="utf-8")
            changed_files.append(path)
        scan_text = normalized if write_mode else original
        for lineno, line in enumerate(scan_text.splitlines(), 1):
            if BAD_REGEX.search(line):
                findings.append((path, lineno, line.strip()))

    if changed_files:
        safe_print("Transcript guard: normalized files:")
        for path in changed_files:
            safe_print(path.relative_to(ROOT))

    if findings:
        safe_print("Transcript guard failed. Possible mojibake found:")
        for path, lineno, line in findings:
            safe_print(f"{path.relative_to(ROOT)}:{lineno}: {line}")
        if not write_mode:
            safe_print("Run: python scripts/transcript_guard.py --write")
        return 1 if check_mode else 0

    safe_print("Transcript guard passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


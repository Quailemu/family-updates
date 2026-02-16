import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: search_text.py <root> <pattern>")
        return 2
    root = Path(sys.argv[1])
    pattern = sys.argv[2]
    matches = 0
    for path in root.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if pattern in text:
            matches += 1
            print(f"{path}:{text.count(pattern)}")
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main())

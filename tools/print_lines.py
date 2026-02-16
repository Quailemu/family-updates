import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: print_lines.py <path> <pattern>")
        return 2
    path = Path(sys.argv[1])
    pattern = sys.argv[2]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 1
    for idx, line in enumerate(lines, 1):
        if pattern in line:
            print(f"{idx}:{line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

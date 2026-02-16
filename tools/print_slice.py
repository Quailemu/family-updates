import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 4:
        print("Usage: print_slice.py <path> <start> <end>")
        return 2
    path = Path(sys.argv[1])
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print(f"ERROR: {exc}")
        return 1
    out = sys.stdout.buffer
    for idx in range(max(1, start), min(len(lines), end) + 1):
        text = f"{idx}:{lines[idx-1]}\n"
        out.write(text.encode("utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

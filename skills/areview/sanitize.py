#!/usr/bin/env python3
"""Strip review provenance from an artifact before a blind round.

Usage: sanitize.py <src> <out> [--extra-words FILE] [--allow FILE] [--report-only]

- Strips 4 leak classes: review trail, resolution markers, intent
  justifications defending past choices, changelog/provenance headers.
- leak_words.txt (next to this script) is loaded by default; --extra-words
  adds domain vocabulary on top.
- --allow FILE: regexes (one per line) for false positives to ignore in
  leak-verify (e.g. 'согласованность', 'unresolved', 'left-aligned').
- On LEAKS > 0: out file is NOT written (removed if created), exit 1.
  Exit 1 on the FIRST run of a real artifact is NORMAL — iterate patterns
  and allowlist until 0; do not weaken the vocabulary.
- --report-only: print leaks without writing anything, exit 0.
"""
import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent

# Class 1-4 strip patterns (EN+RU). Adapt per domain via --extra-words.
STRIP_PATTERNS = [
    # 1. explicit review trail
    r'\s*\((?:fixed|found|caught|исправлено|нашли|найдено) (?:by|в|по)[^)]*\)',
    r'\bREVISION \d+\b', r'\b(?:round|раунд) #?\d+\b', r'\((?:review|ревью) #?\d+\)',
    r'\b(?:blind|anchored|слепой|блайнд)\b[^.\n]*(?:run|round|прогон|раунд)[^.\n]*',
    # 2. resolution markers
    r'\s*—?\s*(?:СОГЛАСОВАНО|ALIGNED|consistent) (?:со?|with) [^.\n]*',
    r'\b(?:ВЕРИФИЦИРОВАНО?|VERIFIED|CONFIRMED|разрешено|dispute (?:settled|resolved)|спор (?:решён|закрыт))\b[^.\n]*',
    # 3. intent justifications defending past choices
    r'\s*\((?:intentional|deliberate|намеренн\w+|осознанн\w+)[^)]*\)',
    r'\s*\(corrected to[^)]*\)', r'\s*\(исправлено на[^)]*\)',
    # 4. changelog/provenance
    r'^\s*(?:Sources?|Источники?):.*_review_.*$',
    r'^\s*(?:Changelog|История правок):.*$',
]


def load_words(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.strip().startswith('#')
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--extra-words', type=Path)
    ap.add_argument('--allow', type=Path)
    ap.add_argument('--report-only', action='store_true')
    args = ap.parse_args()

    text = Path(args.src).read_text()
    for pat in STRIP_PATTERNS:
        text = re.sub(pat, '', text, flags=re.I | re.M)

    words = load_words(HERE / 'leak_words.txt')
    if args.extra_words:
        words += load_words(args.extra_words)
    allow = [re.compile(p, re.I) for p in load_words(args.allow)] if args.allow else []

    leak_re = re.compile('|'.join(words), re.I) if words else None
    leaks = []
    for line in text.splitlines():
        if leak_re and leak_re.search(line):
            if any(a.search(line) for a in allow):
                continue
            leaks.append(line)

    print(f'LEAKS: {len(leaks)}')
    for line in leaks:
        print(f'  > {line.strip()}')

    if args.report_only:
        return 0
    out = Path(args.out)
    if leaks:
        out.unlink(missing_ok=True)  # never leave a leaky "clean" copy
        print('NOT clean — iterate strip patterns / --allow until LEAKS:0 '
              '(exit 1 on first run is normal)', file=sys.stderr)
        return 1
    out.write_text(text)
    print(f'clean copy: {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

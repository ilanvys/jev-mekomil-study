"""Build the results page from results_e2e.csv and report/template.html.

Writes docs/index.html, a complete page that GitHub Pages serves.
With --artifact PATH, also writes the bare page body for a claude.ai artifact.

Usage: .venv/bin/python report/build.py
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from run_e2e import read_rows  # noqa: E402

HEAD = """<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='31' fill='%23F6CF1C' stroke='%23111' stroke-width='2'/%3E%3Crect x='20' y='19' width='6' height='26' fill='%231D3F9E'/%3E%3Crect x='30' y='19' width='6' height='26' fill='%231D3F9E'/%3E%3Crect x='30' y='39' width='15' height='6' fill='%231D3F9E'/%3E%3C/svg%3E">
<style>body { margin: 0; } [hidden] { display: none !important; }</style>
</head>
<body>
"""


def stats(rows, route):
    mine = [r for r in rows if r['route'] == route]
    need = [r for r in mine if r['expected'] != 'NONE']
    none = [r for r in mine if r['expected'] == 'NONE']
    return dict(
        n=len(mine), n_need=len(need),
        need_med=statistics.median(r['total_ms'] for r in need),
        none_med=statistics.median(r['total_ms'] for r in none),
        jev_med=statistics.median(r['jev_ms'] for r in need),
        claude_med=statistics.median(r['claude_ms'] for r in need),
        rounds=statistics.mean(r['rounds'] for r in need),
        cost=sum(r['claude_cost_usd'] + r['jev_cost_usd'] for r in mine),
        followed=sum(r['followed_router'] is True for r in mine),
        correct_need=[sum(r['correct'] for r in need), len(need)],
        errors=sum(1 for r in mine if r['error']),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifact', type=Path, help='also write the page body here')
    args = parser.parse_args()

    rows = read_rows(ROOT / 'results_e2e.csv')
    r1, r2 = stats(rows, 'claude'), stats(rows, 'jev')
    assert r1['errors'] == r2['errors'] == 0
    body = (HERE / 'template.html').read_text().replace('__DATA__', json.dumps(dict(r1=r1, r2=r2)))
    (ROOT / 'docs').mkdir(exist_ok=True)
    (ROOT / 'docs' / 'index.html').write_text(HEAD + body + '\n</body>\n</html>\n')
    if args.artifact:
        args.artifact.write_text(body)
    print(json.dumps(dict(r1=r1, r2=r2), indent=1))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pandas as pd


def filter_file(path: Path, output_dir: Path, min_year: int, max_year: int) -> Dict[str, object]:
    df = pd.read_csv(path)
    if 'Year' not in df.columns:
        raise ValueError(f"Column 'Year' not found in {path.name}")

    year = pd.to_numeric(df['Year'], errors='coerce')
    kept_mask = year.between(min_year, max_year, inclusive='both')
    removed_mask = ~kept_mask

    kept = df.loc[kept_mask].copy()
    removed = df.loc[removed_mask].copy()

    stem = path.stem
    output_name = f'{stem}_{min_year}_{max_year}.csv'
    removed_name = f'{stem}_removed_out_of_range.csv'
    kept_path = output_dir / output_name
    removed_path = output_dir / removed_name

    kept.to_csv(kept_path, index=False)
    if not removed.empty:
        removed.to_csv(removed_path, index=False)

    return {
        'source_file': path.name,
        'output_file': kept_path.name,
        'removed_file': removed_path.name if not removed.empty else None,
        'rows_before': int(len(df)),
        'rows_after': int(len(kept)),
        'rows_removed': int(len(removed)),
        'year_min_before': int(year.min()) if year.notna().any() else None,
        'year_max_before': int(year.max()) if year.notna().any() else None,
        'year_min_after': int(pd.to_numeric(kept['Year'], errors='coerce').min()) if not kept.empty else None,
        'year_max_after': int(pd.to_numeric(kept['Year'], errors='coerce').max()) if not kept.empty else None,
        'removed_years': sorted({int(v) for v in pd.to_numeric(removed['Year'], errors='coerce').dropna().tolist()}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Filter raw Scopus CSV exports to an explicit year window.')
    parser.add_argument('--project-root', type=Path, default=Path.cwd(), help='Root of the project repository.')
    parser.add_argument('--min-year', type=int, default=1985)
    parser.add_argument('--max-year', type=int, default=2025)
    args = parser.parse_args()

    raw_dir = args.project_root / 'Data' / 'raw' / 'scopus'
    clean_dir = args.project_root / 'Data' / 'interim' / 'cleaned'
    docs_dir = args.project_root / 'Data' / 'docs'
    clean_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(raw_dir.glob('*.csv'))
    if not csv_files:
        raise SystemExit(f'No CSV files found in: {raw_dir}')

    logs: List[Dict[str, object]] = []
    for path in csv_files:
        logs.append(filter_file(path, clean_dir, args.min_year, args.max_year))

    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        'generated_at_utc': timestamp,
        'min_year': args.min_year,
        'max_year': args.max_year,
        'files': logs,
    }
    (docs_dir / 'year_filter_log.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    pd.DataFrame(logs).to_csv(docs_dir / 'year_filter_log.csv', index=False)

    print(f'Filtered {len(logs)} CSV file(s). Clean files written to: {clean_dir}')
    for item in logs:
        print(
            f"- {item['source_file']}: {item['rows_before']} -> {item['rows_after']} "
            f"(removed {item['rows_removed']}; removed years={item['removed_years']})"
        )


if __name__ == '__main__':
    main()

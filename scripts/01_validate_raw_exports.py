#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd

EXPECTED_COLUMNS = [
    'Authors', 'Author full names', 'Author(s) ID', 'Title', 'Year', 'Source title',
    'Volume', 'Issue', 'Art. No.', 'Page start', 'Page end', 'Cited by', 'DOI', 'Link',
    'Affiliations', 'Authors with affiliations', 'Abstract', 'Author Keywords',
    'Index Keywords', 'Molecular Sequence Numbers', 'Chemicals/CAS', 'Tradenames',
    'Manufacturers', 'Funding Details', 'Funding Texts', 'References',
    'Correspondence Address', 'Editors', 'Publisher', 'Sponsors', 'Conference name',
    'Conference date', 'Conference location', 'Conference code', 'ISSN', 'ISBN',
    'CODEN', 'PubMed ID', 'Language of Original Document', 'Abbreviated Source Title',
    'Document Type', 'Publication Stage', 'Open Access', 'Source', 'EID'
]

CRITICAL_FIELDS = [
    'Title', 'Year', 'Source title', 'Abstract', 'Author Keywords',
    'Document Type', 'Publication Stage', 'Language of Original Document', 'EID', 'DOI'
]


def infer_corpus_name(path: Path) -> str:
    stem = path.stem.lower()
    if 'prime' in stem or 'linha' in stem or 'aprime' in stem:
        return 'A_prime'
    if re.search(r'(^|_)a($|_)', stem) or stem == 'corpus_a':
        return 'A'
    if re.search(r'(^|_)b($|_)', stem) or stem == 'corpus_b':
        return 'B'
    return path.stem


def safe_read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def split_keywords(series: pd.Series) -> List[str]:
    tokens: List[str] = []
    for value in series.dropna().astype(str):
        for kw in value.split(';'):
            clean = re.sub(r'\s+', ' ', kw.strip())
            if clean:
                tokens.append(clean)
    return tokens


def keyword_stats(df: pd.DataFrame) -> Dict[str, object]:
    raw_keywords = split_keywords(df['Author Keywords']) if 'Author Keywords' in df.columns else []
    raw_series = pd.Series(raw_keywords, dtype='string')
    if raw_series.empty:
        return {
            'author_keywords_total_instances': 0,
            'author_keywords_unique_raw': 0,
            'author_keywords_unique_lower': 0,
            'author_keywords_threshold_ge_2': 0,
            'author_keywords_threshold_ge_5': 0,
            'top_15_author_keywords_lower': [],
        }

    lower_series = raw_series.str.strip().str.lower()
    lower_counts = lower_series.value_counts()
    return {
        'author_keywords_total_instances': int(len(raw_series)),
        'author_keywords_unique_raw': int(raw_series.nunique()),
        'author_keywords_unique_lower': int(lower_series.nunique()),
        'author_keywords_threshold_ge_2': int((lower_counts >= 2).sum()),
        'author_keywords_threshold_ge_5': int((lower_counts >= 5).sum()),
        'top_15_author_keywords_lower': [
            {'keyword': str(idx), 'count': int(val)}
            for idx, val in lower_counts.head(15).items()
        ],
    }


def analyze_file(path: Path, expected_min_year: int, expected_max_year: int) -> Dict[str, object]:
    df = safe_read_csv(path)
    result: Dict[str, object] = {
        'file_name': path.name,
        'corpus': infer_corpus_name(path),
        'rows': int(len(df)),
        'columns': int(df.shape[1]),
        'expected_columns_match': list(df.columns) == EXPECTED_COLUMNS,
        'missing_expected_columns': [c for c in EXPECTED_COLUMNS if c not in df.columns],
        'extra_columns': [c for c in df.columns if c not in EXPECTED_COLUMNS],
    }

    year = pd.to_numeric(df.get('Year'), errors='coerce')
    result.update({
        'year_min': int(year.min()) if year.notna().any() else None,
        'year_max': int(year.max()) if year.notna().any() else None,
        'records_below_min_year': int((year < expected_min_year).sum()) if year.notna().any() else 0,
        'records_above_max_year': int((year > expected_max_year).sum()) if year.notna().any() else 0,
        'years_above_max': sorted({int(v) for v in year.dropna() if v > expected_max_year}),
        'years_below_min': sorted({int(v) for v in year.dropna() if v < expected_min_year}),
    })

    if 'EID' in df.columns:
        eid = df['EID'].astype('string').str.strip()
        result['duplicate_eid_rows'] = int(eid.duplicated().sum())
        result['missing_eid_rows'] = int(eid.isna().sum())
    else:
        result['duplicate_eid_rows'] = None
        result['missing_eid_rows'] = None

    if 'DOI' in df.columns:
        doi = df['DOI'].astype('string').str.strip().str.lower()
        doi_non_empty = doi.replace({'': pd.NA}).dropna()
        result['duplicate_doi_rows_non_empty'] = int(doi_non_empty.duplicated().sum())
        result['missing_doi_rows'] = int(doi.isna().sum() + (doi == '').sum())
    else:
        result['duplicate_doi_rows_non_empty'] = None
        result['missing_doi_rows'] = None

    for field in CRITICAL_FIELDS:
        if field in df.columns:
            miss = df[field].isna().sum()
            if df[field].dtype == object:
                miss += (df[field].astype('string').str.strip() == '').sum()
            result[f'missing_pct__{field}'] = round((miss / len(df)) * 100, 2) if len(df) else 0.0
        else:
            result[f'missing_pct__{field}'] = None

    for col in ['Document Type', 'Publication Stage', 'Language of Original Document', 'Open Access']:
        if col in df.columns:
            counts = df[col].fillna('[MISSING]').astype(str).value_counts().to_dict()
            result[f'value_counts__{col}'] = {str(k): int(v) for k, v in counts.items()}

    result.update(keyword_stats(df))
    return result


def write_outputs(results: List[Dict[str, object]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = output_dir / 'Data' / 'docs'
    audits_dir = output_dir / 'Data' / 'interim' / 'keyword_audits'
    docs_dir.mkdir(parents=True, exist_ok=True)
    audits_dir.mkdir(parents=True, exist_ok=True)

    json_path = docs_dir / 'raw_validation_report.json'
    with json_path.open('w', encoding='utf-8') as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)

    flat_rows = []
    for item in results:
        row = {k: v for k, v in item.items() if not isinstance(v, (dict, list))}
        flat_rows.append(row)
    pd.DataFrame(flat_rows).to_csv(docs_dir / 'raw_validation_report.csv', index=False)

    md_path = docs_dir / 'raw_validation_report.md'
    lines = [
        '# Raw Scopus export validation report',
        '',
        'This report was generated automatically from the CSV files in `Data/raw/scopus/`.',
        ''
    ]
    for item in results:
        lines += [
            f"## {item['file_name']}",
            '',
            f"- Corpus: `{item['corpus']}`",
            f"- Rows: **{item['rows']}**",
            f"- Columns: **{item['columns']}**",
            f"- Expected Scopus 45-column schema match: **{item['expected_columns_match']}**",
            f"- Year range found: **{item['year_min']}–{item['year_max']}**",
            f"- Records above max year: **{item['records_above_max_year']}**",
            f"- Records below min year: **{item['records_below_min_year']}**",
            f"- Duplicate EID rows: **{item['duplicate_eid_rows']}**",
            f"- Duplicate non-empty DOI rows: **{item['duplicate_doi_rows_non_empty']}**",
            '',
            '### Distribution snapshots',
            '',
        ]
        for col in ['Document Type', 'Publication Stage', 'Language of Original Document', 'Open Access']:
            counts = item.get(f'value_counts__{col}', {})
            if counts:
                lines.append(f"- {col}: {counts}")
        lines += [
            '',
            '### Missing percentages',
            '',
        ]
        for field in CRITICAL_FIELDS:
            lines.append(f"- {field}: {item.get(f'missing_pct__{field}', 'NA')}%")
        lines += [
            '',
            '### Author keyword summary',
            '',
            f"- Total author keyword instances: **{item['author_keywords_total_instances']}**",
            f"- Unique raw author keywords: **{item['author_keywords_unique_raw']}**",
            f"- Unique lowercased author keywords: **{item['author_keywords_unique_lower']}**",
            f"- Terms with frequency ≥ 2: **{item['author_keywords_threshold_ge_2']}**",
            f"- Terms with frequency ≥ 5: **{item['author_keywords_threshold_ge_5']}**",
            '',
            '| Top lowercased keyword | Count |',
            '|---|---:|',
        ]
        for entry in item['top_15_author_keywords_lower']:
            lines.append(f"| {entry['keyword']} | {entry['count']} |")
        lines += ['', '---', '']
    md_path.write_text('\n'.join(lines), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='Validate raw Scopus CSV exports for corpora A, A_prime, and B.')
    parser.add_argument('--project-root', type=Path, default=Path.cwd(), help='Root of the project repository.')
    parser.add_argument('--expected-min-year', type=int, default=1985)
    parser.add_argument('--expected-max-year', type=int, default=2025)
    args = parser.parse_args()

    raw_dir = args.project_root / 'Data' / 'raw' / 'scopus'
    if not raw_dir.exists():
        raise SystemExit(f'Raw directory not found: {raw_dir}')

    csv_files = sorted(raw_dir.glob('*.csv'))
    if not csv_files:
        raise SystemExit(f'No CSV files found in: {raw_dir}')

    results = [analyze_file(path, args.expected_min_year, args.expected_max_year) for path in csv_files]
    write_outputs(results, args.project_root)

    print(f'Validated {len(results)} CSV file(s). Reports written to: {args.project_root / "Data" / "docs"}')
    for item in results:
        print(
            f"- {item['file_name']}: rows={item['rows']}, years={item['year_min']}-{item['year_max']}, "
            f"above_max={item['records_above_max_year']}, dup_eid={item['duplicate_eid_rows']}"
        )


if __name__ == '__main__':
    main()

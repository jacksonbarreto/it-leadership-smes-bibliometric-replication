#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd


def split_keywords(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        if pd.isna(value):
            continue
        for kw in str(value).split(';'):
            clean = re.sub(r'\s+', ' ', kw.strip())
            if clean:
                out.append(clean)
    return out


def lower_norm(s: str) -> str:
    return re.sub(r'\s+', ' ', s.strip().lower())


def singularize_naive(s: str) -> str:
    s = s.strip().lower()
    if s.endswith('ies') and len(s) > 4:
        return s[:-3] + 'y'
    if s.endswith('sses') or s.endswith('ss'):
        return s
    if s.endswith('s') and len(s) > 3:
        return s[:-1]
    return s


def build_variant_groups(keyword_counts: pd.Series) -> List[Tuple[str, List[Tuple[str, int]]]]:
    groups: Dict[str, List[Tuple[str, int]]] = {}
    for keyword, count in keyword_counts.items():
        key = singularize_naive(lower_norm(keyword))
        groups.setdefault(key, []).append((keyword, int(count)))

    multi_variant = []
    for base, variants in groups.items():
        normalized_forms = {lower_norm(v[0]) for v in variants}
        if len(normalized_forms) > 1:
            multi_variant.append((base, sorted(variants, key=lambda x: (-x[1], x[0].lower()))))
    multi_variant.sort(key=lambda x: (-sum(c for _, c in x[1]), x[0]))
    return multi_variant


def process_file(path: Path, output_dir: Path) -> None:
    df = pd.read_csv(path)
    keywords = split_keywords(df.get('Author Keywords', pd.Series(dtype='string')))
    raw_counts = pd.Series(keywords, dtype='string').value_counts()
    lower_counts = pd.Series([lower_norm(k) for k in keywords], dtype='string').value_counts()

    corpus_dir = output_dir / path.stem
    corpus_dir.mkdir(parents=True, exist_ok=True)

    raw_counts.rename_axis('keyword').reset_index(name='count').to_csv(corpus_dir / 'author_keywords_raw_counts.csv', index=False)
    lower_counts.rename_axis('keyword_lower').reset_index(name='count').to_csv(corpus_dir / 'author_keywords_lower_counts.csv', index=False)

    groups = build_variant_groups(raw_counts)
    rows = []
    for base, variants in groups:
        total = sum(c for _, c in variants)
        for keyword, count in variants:
            rows.append({
                'variant_group_key': base,
                'variant': keyword,
                'count': count,
                'group_total': total,
            })
    pd.DataFrame(rows).to_csv(corpus_dir / 'candidate_variant_groups.csv', index=False)

    sample_path = corpus_dir / 'thesaurus_seed.txt'
    lines = ['label\treplace by']
    for base, variants in groups[:50]:
        canonical = variants[0][0]
        for keyword, _count in variants:
            if keyword != canonical:
                lines.append(f'{keyword}\t{canonical}')
    sample_path.write_text('\n'.join(lines), encoding='utf-8')

    print(f'Keyword inventory written for {path.name} -> {corpus_dir}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Create keyword inventories and a thesaurus seed from cleaned Scopus CSVs.')
    parser.add_argument('--project-root', type=Path, default=Path.cwd(), help='Root of the project repository.')
    args = parser.parse_args()

    clean_dir = args.project_root / 'Data' / 'interim' / 'cleaned'
    output_dir = args.project_root / 'Data' / 'interim' / 'keyword_audits'
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_files = sorted([p for p in clean_dir.glob('*.csv') if 'removed_out_of_range' not in p.name])
    if not csv_files:
        raise SystemExit(f'No cleaned CSV files found in: {clean_dir}')

    for path in csv_files:
        process_file(path, output_dir)


if __name__ == '__main__':
    main()

# Validation and cleaning scripts for the Scopus corpora

These scripts assume the following repository structure:

```text
project_root/
├── Data/
│   ├── raw/
│   │   └── scopus/
│   │       ├── corpus_A.csv
│   │       ├── corpus_A_prime.csv
│   │       └── corpus_B.csv
│   ├── interim/
│   │   ├── cleaned/
│   │   └── keyword_audits/
│   └── docs/
├── scripts/
└── manuscript/
```

## 1) Validate raw exports

```bash
python scripts/01_validate_raw_exports.py --project-root .
```

Outputs:
- `Data/docs/raw_validation_report.json`
- `Data/docs/raw_validation_report.csv`
- `Data/docs/raw_validation_report.md`

## 2) Filter years to the intended time window

```bash
python scripts/02_filter_years.py --project-root . --min-year 1985 --max-year 2025
```

Outputs:
- cleaned CSV files in `Data/interim/cleaned/`
- `Data/docs/year_filter_log.json`
- `Data/docs/year_filter_log.csv`

## 3) Build keyword inventories and a thesaurus seed

```bash
python scripts/03_keyword_inventory.py --project-root .
```

Outputs, for each cleaned corpus:
- `author_keywords_raw_counts.csv`
- `author_keywords_lower_counts.csv`
- `candidate_variant_groups.csv`
- `thesaurus_seed.txt`

## Notes

- Keep the original Scopus CSV exports untouched in `Data/raw/scopus/`.
- Treat the files in `Data/interim/cleaned/` as the authoritative study corpora after filtering.
- Review `thesaurus_seed.txt` manually before using it in VOSviewer.

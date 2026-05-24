#!/usr/bin/env python3
"""Build a scientist-editable phenotype mapping TSV for a sample sheet."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


COLUMNS = [
    "sample_name",
    "sra_run_id",
    "biosample_accession",
    "bioproject_id",
    "paper_sample_id",
    "primary_group",
    "case_control_status",
    "disease_or_condition",
    "timepoint",
    "treatment_group",
    "subject_id",
    "matched_from",
    "mapping_confidence",
    "evidence",
    "notes",
]


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_candidates(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("phenotype_mapping_candidates") or data.get("sample_group_mappings") or []


def _norm(value: object) -> str:
    return str(value or "").strip()


def _candidate_values(candidate: dict, *keys: str) -> set[str]:
    return {_norm(candidate.get(key)) for key in keys if _norm(candidate.get(key))}


def _row_values(row: dict) -> set[str]:
    return {_norm(value) for value in row.values() if _norm(value)}


def match_candidate(row: dict, candidates: list[dict]) -> tuple[dict | None, str]:
    """Match one sample-sheet row to the best phenotype candidate.

    Priority:
    1. exact SRA run ID
    2. exact BioSample accession
    3. exact sample_name
    4. candidate paper_sample_id found in any BioSample/sample-sheet attribute
    """
    sra_run_id = _norm(row.get("sra_run_id"))
    biosample_accession = _norm(row.get("biosample_accession"))
    sample_name = _norm(row.get("sample_name"))
    row_values = _row_values(row)

    for candidate in candidates:
        if sra_run_id and sra_run_id in _candidate_values(candidate, "sra_run_id", "run_accession"):
            return candidate, "sra_run_id"

    for candidate in candidates:
        if biosample_accession and biosample_accession in _candidate_values(
            candidate, "biosample_accession", "biosample", "biosample_id"
        ):
            return candidate, "biosample_accession"

    for candidate in candidates:
        if sample_name and sample_name in _candidate_values(candidate, "sample_name", "paper_sample_id", "sample_id"):
            return candidate, "sample_name"

    for candidate in candidates:
        paper_sample_id = _norm(candidate.get("paper_sample_id") or candidate.get("sample_id"))
        if paper_sample_id and paper_sample_id in row_values:
            return candidate, "biosample_attribute"

    return None, "unmatched"


def mapping_row(sample_row: dict, candidate: dict | None, matched_from: str) -> dict:
    if candidate is None:
        return {
            "sample_name": sample_row.get("sample_name", ""),
            "sra_run_id": sample_row.get("sra_run_id", ""),
            "biosample_accession": sample_row.get("biosample_accession", ""),
            "bioproject_id": sample_row.get("bioproject_id", ""),
            "paper_sample_id": "",
            "primary_group": "unknown",
            "case_control_status": "",
            "disease_or_condition": "",
            "timepoint": "",
            "treatment_group": "",
            "subject_id": "",
            "matched_from": matched_from,
            "mapping_confidence": "low",
            "evidence": "",
            "notes": "No per-sample phenotype mapping found in paper/supplement evidence.",
        }

    return {
        "sample_name": sample_row.get("sample_name", ""),
        "sra_run_id": sample_row.get("sra_run_id", ""),
        "biosample_accession": sample_row.get("biosample_accession", ""),
        "bioproject_id": sample_row.get("bioproject_id", ""),
        "paper_sample_id": candidate.get("paper_sample_id") or candidate.get("sample_id") or "",
        "primary_group": candidate.get("primary_group") or candidate.get("group") or candidate.get("group_name") or "unknown",
        "case_control_status": candidate.get("case_control_status", ""),
        "disease_or_condition": candidate.get("disease_or_condition") or candidate.get("condition") or "",
        "timepoint": candidate.get("timepoint", ""),
        "treatment_group": candidate.get("treatment_group", ""),
        "subject_id": candidate.get("subject_id", ""),
        "matched_from": matched_from,
        "mapping_confidence": candidate.get("mapping_confidence") or candidate.get("confidence") or "medium",
        "evidence": candidate.get("evidence", ""),
        "notes": candidate.get("notes", ""),
    }


def build_mapping(sample_rows: list[dict], candidates: list[dict]) -> list[dict]:
    rows = []
    for sample_row in sample_rows:
        candidate, matched_from = match_candidate(sample_row, candidates)
        rows.append(mapping_row(sample_row, candidate, matched_from))
    return rows


def write_mapping(rows: list[dict], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sample_sheet_tsv", type=Path)
    parser.add_argument("--llm-reading", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sample_rows = read_tsv(args.sample_sheet_tsv)
    candidates = load_candidates(args.llm_reading)
    rows = build_mapping(sample_rows, candidates)
    write_mapping(rows, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build a generic SRA sample sheet TSV from retrieved NCBI metadata."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


LEADING_COLUMNS = [
    "sample_name",
    "sra_run_id",
    "biosample_accession",
    "bioproject_id",
    "experiment_accession",
    "platform",
    "library_strategy",
    "library_source",
    "library_selection",
]


def rows_from_metadata(metadata: dict) -> list[dict]:
    rows = []
    for project in metadata.get("bioprojects", []):
        bp_id = project.get("bioproject_id", "")
        biosample_attrs = {}
        for biosample in project.get("biosamples", []):
            accession = biosample.get("accession") or biosample.get("biosample_id", "")
            biosample_attrs[accession] = biosample.get("attributes", {})

        for run in project.get("sra_runs", []):
            bs_acc = run.get("biosample_accession", "")
            attrs = biosample_attrs.get(bs_acc, {})
            sample_name = attrs.get("sample_name") or attrs.get("Sample Name") or bs_acc or run.get("run_accession", "")
            row = {
                "sample_name": sample_name,
                "sra_run_id": run.get("run_accession", ""),
                "biosample_accession": bs_acc,
                "bioproject_id": run.get("bioproject_id") or bp_id,
                "experiment_accession": run.get("experiment_accession", ""),
                "platform": run.get("platform", ""),
                "library_strategy": run.get("library_strategy", ""),
                "library_source": run.get("library_source", ""),
                "library_selection": run.get("library_selection", ""),
            }
            row.update(attrs)
            rows.append(row)
    return rows


def write_tsv(rows: list[dict], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    extra_columns = sorted({key for row in rows for key in row if key not in LEADING_COLUMNS})
    columns = LEADING_COLUMNS + extra_columns
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return output


def report_markdown(metadata: dict, rows: list[dict]) -> str:
    project_count = len(metadata.get("bioprojects", []))
    unresolved = metadata.get("unresolved", [])
    lines = [
        "# Paper to Sample Sheet Report",
        "",
        f"- BioProjects resolved: {project_count}",
        f"- SRA runs in sample sheet: {len(rows)}",
        f"- Unresolved accessions: {len(unresolved)}",
    ]
    if unresolved:
        lines.append("")
        lines.append("## Unresolved Accessions")
        for item in unresolved:
            lines.append(f"- `{item.get('id')}` ({item.get('type')}): {item.get('reason')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata_json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    metadata = json.loads(args.metadata_json.read_text(encoding="utf-8"))
    rows = rows_from_metadata(metadata)
    write_tsv(rows, args.output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report_markdown(metadata, rows), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

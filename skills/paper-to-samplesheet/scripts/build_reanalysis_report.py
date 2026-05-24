#!/usr/bin/env python3
"""Build a scientist-readable Markdown report for FASTQ reanalysis planning."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def read_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _value(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", []):
            return str(value)
    return "Not reported"


def _markdown_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    if not rows:
        return ["Not available."]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) if cell not in (None, "") else "" for cell in row) + " |")
    return lines


def _group_counts(mapping_rows: list[dict]) -> list[list[object]]:
    counts = Counter(row.get("primary_group") or "unknown" for row in mapping_rows)
    return [[group, count] for group, count in sorted(counts.items())]


def _confidence_counts(mapping_rows: list[dict]) -> list[list[object]]:
    counts = Counter(row.get("mapping_confidence") or "unknown" for row in mapping_rows)
    return [[confidence, count] for confidence, count in sorted(counts.items())]


def _public_data_rows(metadata: dict) -> list[list[object]]:
    rows = []
    for project in metadata.get("bioprojects", []):
        rows.append(
            [
                project.get("bioproject_id", ""),
                project.get("biosample_count", len(project.get("biosamples", []))),
                project.get("sra_run_count", len(project.get("sra_runs", []))),
            ]
        )
    return rows


def _sequencing_details(llm: dict, sample_rows: list[dict]) -> list[list[object]]:
    study = llm.get("study_metadata", {})
    protocol = llm.get("sequencing_protocol", {})
    platforms = sorted({row.get("platform", "") for row in sample_rows if row.get("platform")})
    strategies = sorted({row.get("library_strategy", "") for row in sample_rows if row.get("library_strategy")})
    return [
        ["Sample type", _value(study, "sample_type")],
        ["Sequencing platform", _value(protocol, "sequencing_platform", "platform") if protocol else ", ".join(platforms) or "Not reported"],
        ["Library strategy", _value(protocol, "library_strategy") if protocol else ", ".join(strategies) or "Not reported"],
        ["Target region", _value(protocol, "target_region") if protocol else _value(study, "target_region")],
        ["Primers", _value(protocol, "primers", "primer_sequences") if protocol else "Not reported"],
        ["Read layout / length", _value(protocol, "read_layout", "read_length") if protocol else "Not reported"],
    ]


def build_report(
    sample_rows: list[dict],
    mapping_rows: list[dict],
    metadata: dict,
    llm: dict,
    manifest: dict | None = None,
) -> str:
    study = llm.get("study_metadata", {})
    unresolved = metadata.get("unresolved", [])
    low_conf = [row for row in mapping_rows if (row.get("mapping_confidence") or "").lower() == "low"]
    unmatched = [row for row in mapping_rows if row.get("matched_from") == "unmatched"]
    paper_count = study.get("sample_count")

    lines = [
        "# Reanalysis Report",
        "",
        "This report summarizes the paper package in a form intended for scientists planning raw FASTQ reanalysis.",
        "",
        "## Study Overview",
        "",
        * _markdown_table(
            ["Field", "Value"],
            [
                ["Title", _value(study, "title")],
                ["Reported sample count", paper_count if paper_count not in (None, "") else "Not reported"],
                ["Sample type", _value(study, "sample_type")],
                ["Study design", _value(study, "study_design")],
            ],
        ),
        "",
        "## Public Data Found",
        "",
        * _markdown_table(["BioProject", "BioSamples", "SRA runs"], _public_data_rows(metadata)),
        "",
        f"Rows in `sample_sheet.tsv`: {len(sample_rows)}",
        "",
        "## Phenotype Mapping Summary",
        "",
        "`phenotype_mapping.tsv` is the editable bridge between the SRA sample sheet and paper/supplement phenotype labels.",
        "",
        * _markdown_table(["Primary group", "Rows"], _group_counts(mapping_rows)),
        "",
        * _markdown_table(["Mapping confidence", "Rows"], _confidence_counts(mapping_rows)),
        "",
        "## Sequencing Details",
        "",
        * _markdown_table(["Field", "Value"], _sequencing_details(llm, sample_rows)),
        "",
        "## Sample Count Audit",
        "",
        * _markdown_table(
            ["Source", "Count"],
            [
                ["Paper/supplement reported", paper_count if paper_count not in (None, "") else "Not reported"],
                ["Rows in sample_sheet.tsv", len(sample_rows)],
                ["Rows in phenotype_mapping.tsv", len(mapping_rows)],
                ["Unmatched phenotype rows", len(unmatched)],
                ["Low-confidence phenotype rows", len(low_conf)],
            ],
        ),
        "",
        "## Recommended Reanalysis Design",
        "",
    ]

    design = llm.get("recommended_reanalysis_design") or {}
    if design:
        lines.extend(_markdown_table(["Item", "Recommendation"], [[key, value] for key, value in design.items()]))
    else:
        lines.extend(
            [
                "- Use `sample_sheet.tsv` to download or organize SRA FASTQ files.",
                "- Join `sample_sheet.tsv` with `phenotype_mapping.tsv` before group-level analysis.",
                "- Review low-confidence or unmatched phenotype rows before differential abundance or diversity testing.",
            ]
        )

    lines.extend(["", "## Warnings and Open Questions", ""])
    warnings = []
    warnings.extend(llm.get("warnings") or [])
    warnings.extend([f"Unresolved accession `{item.get('id')}`: {item.get('reason')}" for item in unresolved])
    if low_conf:
        warnings.append(f"{len(low_conf)} phenotype rows have low-confidence mappings.")
    if unmatched:
        warnings.append(f"{len(unmatched)} phenotype rows could not be matched to paper/supplement sample identifiers.")
    if paper_count not in (None, "") and str(paper_count).isdigit() and int(paper_count) != len(sample_rows):
        warnings.append(f"Paper reports {paper_count} samples, but sample_sheet.tsv has {len(sample_rows)} rows.")
    if warnings:
        lines.extend([f"- {warning}" for warning in warnings])
    else:
        lines.append("- No major warnings detected from the available metadata.")

    lines.extend(["", "## Evidence Notes", ""])
    evidence_rows = [
        [
            row.get("sample_name", ""),
            row.get("primary_group", ""),
            row.get("mapping_confidence", ""),
            row.get("evidence", ""),
        ]
        for row in mapping_rows
        if row.get("evidence")
    ][:20]
    lines.extend(_markdown_table(["Sample", "Group", "Confidence", "Evidence"], evidence_rows))

    if manifest:
        converted = [Path(item.get("file", "")).name for item in manifest.get("files", []) if item.get("status") in {"converted", "copied"}]
        lines.extend(["", "## Files Read", ""])
        lines.extend([f"- {name}" for name in converted] or ["- Not available"])

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-sheet", type=Path, required=True)
    parser.add_argument("--phenotype-mapping", type=Path, required=True)
    parser.add_argument("--ncbi-metadata", type=Path, required=True)
    parser.add_argument("--llm-reading", type=Path, default=None)
    parser.add_argument("--conversion-manifest", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(
        sample_rows=read_tsv(args.sample_sheet),
        mapping_rows=read_tsv(args.phenotype_mapping),
        metadata=read_json(args.ncbi_metadata),
        llm=read_json(args.llm_reading),
        manifest=read_json(args.conversion_manifest),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

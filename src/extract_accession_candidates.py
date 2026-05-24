#!/usr/bin/env python3
"""Find NCBI accession candidates in converted paper artifacts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


ACCESSION_PATTERNS = {
    "bioproject": re.compile(r"\b(?:PRJNA|PRJEB|PRJDB)\d+\b", re.IGNORECASE),
    "sra_run": re.compile(r"\b(?:SRR|ERR|DRR)\d+\b", re.IGNORECASE),
    "sra_experiment": re.compile(r"\b(?:SRX|ERX|DRX)\d+\b", re.IGNORECASE),
    "biosample": re.compile(r"\b(?:SAMN|SAMEA|SAMD)\d+\b", re.IGNORECASE),
}


@dataclass(frozen=True)
class AccessionCandidate:
    id: str
    type: str
    source_file: str
    evidence: str
    confidence: str = "medium"


def _evidence(text: str, start: int, end: int, width: int = 120) -> str:
    left = max(0, start - width)
    right = min(len(text), end + width)
    return re.sub(r"\s+", " ", text[left:right]).strip()


def scan_text(text: str, source_file: str) -> list[AccessionCandidate]:
    candidates: list[AccessionCandidate] = []
    for acc_type, pattern in ACCESSION_PATTERNS.items():
        for match in pattern.finditer(text):
            candidates.append(
                AccessionCandidate(
                    id=match.group(0).upper(),
                    type=acc_type,
                    source_file=source_file,
                    evidence=_evidence(text, match.start(), match.end()),
                    confidence="high" if acc_type == "bioproject" else "medium",
                )
            )
    return candidates


def scan_folder(folder: Path) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    results: list[dict] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".tsv", ".csv"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for candidate in scan_text(text, str(path.relative_to(folder))):
            key = (candidate.id, candidate.type, candidate.source_file)
            if key in seen:
                continue
            seen.add(key)
            results.append(asdict(candidate))
    return results


def normalize_llm_type(value: str) -> str:
    value = (value or "").strip().lower()
    aliases = {
        "run": "sra_run",
        "sra": "sra_run",
        "srr": "sra_run",
        "err": "sra_run",
        "drr": "sra_run",
        "experiment": "sra_experiment",
        "srx": "sra_experiment",
        "erx": "sra_experiment",
        "drx": "sra_experiment",
        "project": "bioproject",
        "bio_project": "bioproject",
        "sample": "biosample",
        "bio_sample": "biosample",
    }
    return aliases.get(value, value)


def reconcile_accessions(regex_results: list[dict], llm_results: list[dict]) -> dict:
    merged: dict[tuple[str, str], dict] = {}

    for source, records in (("regex", regex_results), ("llm", llm_results)):
        for record in records or []:
            acc_id = str(record.get("id", "")).strip().upper()
            acc_type = normalize_llm_type(str(record.get("type", "")))
            if not acc_id or acc_type not in ACCESSION_PATTERNS:
                continue
            key = (acc_id, acc_type)
            current = merged.get(key)
            incoming = {
                "id": acc_id,
                "type": acc_type,
                "source_file": record.get("source_file", ""),
                "evidence": record.get("evidence", ""),
                "confidence": record.get("confidence", "medium"),
                "sources": [source],
            }
            if current is None:
                merged[key] = incoming
                continue
            if source not in current["sources"]:
                current["sources"].append(source)
            if not current.get("evidence") and incoming.get("evidence"):
                current["evidence"] = incoming["evidence"]
            if incoming.get("confidence") == "high":
                current["confidence"] = "high"

    accessions = sorted(merged.values(), key=lambda r: (r["type"], r["id"]))
    return {"accessions": accessions}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("converted_folder", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    results = scan_folder(args.converted_folder)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"accessions": results}, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

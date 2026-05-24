#!/usr/bin/env python3
"""LangGraph orchestration for the paper-to-samplesheet workflow."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, TypedDict

import build_phenotype_mapping
import build_reanalysis_report
import build_sample_sheet
import convert_documents
import extract_accession_candidates
import retrieve_ncbi


class GraphState(TypedDict, total=False):
    input_folder: str
    output_folder: str
    converted_folder: str
    conversion_manifest: dict[str, Any]
    regex_accessions: dict[str, Any]
    llm_reading: dict[str, Any]
    accessions: dict[str, Any]
    ncbi_metadata: dict[str, Any]
    sample_sheet_path: str
    phenotype_mapping_path: str
    reanalysis_report_path: str
    review_packets: dict[str, str]
    warnings: list[str]
    llm_reading_path: str
    ncbi_metadata_path: str
    email: str
    api_key: str | None
    rate_limit: int


EMPTY_LLM_READING: dict[str, Any] = {
    "accessions": [],
    "study_metadata": {},
    "sample_group_mappings": [],
    "phenotype_mapping_candidates": [],
    "sequencing_protocol": {},
    "recommended_reanalysis_design": {},
    "data_availability_notes": [],
    "warnings": [],
}


def initial_state(
    input_folder: Path,
    output_folder: Path | None = None,
    *,
    llm_reading_path: Path | None = None,
    ncbi_metadata_path: Path | None = None,
    email: str = "researcher@example.com",
    api_key: str | None = None,
    rate_limit: int = 3,
) -> GraphState:
    resolved_input = input_folder.resolve()
    resolved_output = (output_folder or Path("outputs") / resolved_input.name).resolve()
    state: GraphState = {
        "input_folder": str(resolved_input),
        "output_folder": str(resolved_output),
        "converted_folder": str(resolved_output / "converted"),
        "review_packets": {},
        "warnings": [],
        "email": email,
        "api_key": api_key,
        "rate_limit": rate_limit,
    }
    if llm_reading_path is not None:
        state["llm_reading_path"] = str(llm_reading_path.resolve())
    if ncbi_metadata_path is not None:
        state["ncbi_metadata_path"] = str(ncbi_metadata_path.resolve())
    return state


def _output_path(state: GraphState, name: str) -> Path:
    return Path(state["output_folder"]) / name


def _write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "Not available.\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell or "") for cell in row) + " |")
    return "\n".join(lines) + "\n"


def conversion_node(state: GraphState) -> GraphState:
    manifest = convert_documents.convert_folder(Path(state["input_folder"]), Path(state["converted_folder"]))
    return {"conversion_manifest": manifest}


def regex_accession_node(state: GraphState) -> GraphState:
    regex_results = extract_accession_candidates.scan_folder(Path(state["converted_folder"]))
    payload = {"accessions": regex_results}
    _write_json(_output_path(state, "regex_accessions.json"), payload)
    return {"regex_accessions": payload}


def llm_reading_node(state: GraphState) -> GraphState:
    llm_path = Path(state["llm_reading_path"]) if state.get("llm_reading_path") else None
    llm = _read_json(llm_path) or dict(EMPTY_LLM_READING)
    output = _output_path(state, "llm_reading.json")
    _write_json(output, llm)
    return {"llm_reading": llm, "llm_reading_path": str(output)}


def build_accession_review(regex_payload: dict[str, Any], llm: dict[str, Any], merged: dict[str, Any]) -> str:
    regex_rows = regex_payload.get("accessions", [])
    llm_rows = llm.get("accessions", [])
    accepted_rows = merged.get("accessions", [])
    accepted_ids = {row.get("id") for row in accepted_rows}
    warnings: list[str] = []
    if not any(row.get("type") == "bioproject" for row in accepted_rows):
        warnings.append("No BioProject accession was accepted. The workflow will resolve SRA or BioSample IDs when possible.")
    low_confidence = [row for row in accepted_rows if row.get("confidence") == "low"]
    if low_confidence:
        warnings.append(f"{len(low_confidence)} accepted accessions have low confidence.")
    llm_only = sorted({row.get("id") for row in llm_rows if row.get("id")} - {row.get("id") for row in regex_rows})
    regex_only = sorted({row.get("id") for row in regex_rows if row.get("id")} - {row.get("id") for row in llm_rows})

    lines = [
        "# Accession Review",
        "",
        "## Accepted Accessions",
        "",
        _table(
            ["Accession", "Type", "Sources", "Confidence", "Evidence"],
            [
                [row.get("id"), row.get("type"), ", ".join(row.get("sources", [])), row.get("confidence"), row.get("evidence")]
                for row in accepted_rows
            ],
        ).rstrip(),
        "",
        "## Source Differences",
        "",
        f"- Regex-only candidates: {', '.join(regex_only) if regex_only else 'None'}",
        f"- LLM-only candidates: {', '.join(llm_only) if llm_only else 'None'}",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {warning}" for warning in warnings] or ["- No accession review warnings."])
    missing = sorted(({row.get("id") for row in regex_rows + llm_rows if row.get("id")} - accepted_ids))
    if missing:
        lines.extend(["", "## Not Accepted", "", ", ".join(missing)])
    return "\n".join(lines).rstrip() + "\n"


def reconcile_accession_node(state: GraphState) -> GraphState:
    regex_payload = state.get("regex_accessions", {"accessions": []})
    llm = state.get("llm_reading", EMPTY_LLM_READING)
    merged = extract_accession_candidates.reconcile_accessions(
        regex_payload.get("accessions", []),
        llm.get("accessions", []),
    )
    _write_json(_output_path(state, "accessions.json"), merged)
    review_path = _output_path(state, "review_accessions.md")
    review_path.write_text(build_accession_review(regex_payload, llm, merged), encoding="utf-8")
    packets = dict(state.get("review_packets", {}))
    packets["accessions"] = str(review_path)
    return {"accessions": merged, "review_packets": packets}


def ncbi_retrieval_node(state: GraphState) -> GraphState:
    existing_path = Path(state["ncbi_metadata_path"]) if state.get("ncbi_metadata_path") else None
    if existing_path and existing_path.exists():
        metadata = _read_json(existing_path)
    else:
        metadata = retrieve_ncbi.resolve_accessions(
            state.get("accessions", {}).get("accessions", []),
            state.get("email", "researcher@example.com"),
            state.get("api_key"),
            int(state.get("rate_limit", 3)),
        )
    output = _output_path(state, "ncbi_metadata.json")
    _write_json(output, metadata)
    return {"ncbi_metadata": metadata, "ncbi_metadata_path": str(output)}


def sample_sheet_node(state: GraphState) -> GraphState:
    rows = build_sample_sheet.rows_from_metadata(state.get("ncbi_metadata", {}))
    output = _output_path(state, "sample_sheet.tsv")
    build_sample_sheet.write_tsv(rows, output)
    return {"sample_sheet_path": str(output)}


def phenotype_mapping_node(state: GraphState) -> GraphState:
    sample_rows = _read_tsv(Path(state["sample_sheet_path"]))
    candidates = (state.get("llm_reading") or {}).get("phenotype_mapping_candidates") or (
        state.get("llm_reading") or {}
    ).get("sample_group_mappings") or []
    rows = build_phenotype_mapping.build_mapping(sample_rows, candidates)
    output = _output_path(state, "phenotype_mapping.tsv")
    build_phenotype_mapping.write_mapping(rows, output)
    return {"phenotype_mapping_path": str(output)}


def build_sample_count_review(llm: dict[str, Any], metadata: dict[str, Any], sample_rows: list[dict[str, str]]) -> str:
    paper_count = (llm.get("study_metadata") or {}).get("sample_count")
    project_rows = [
        [
            project.get("bioproject_id", ""),
            project.get("biosample_count", len(project.get("biosamples", []))),
            project.get("sra_run_count", len(project.get("sra_runs", []))),
        ]
        for project in metadata.get("bioprojects", [])
    ]
    warnings: list[str] = []
    if paper_count not in (None, "") and str(paper_count).isdigit() and int(paper_count) != len(sample_rows):
        warnings.append(f"Paper reports {paper_count} samples, but sample_sheet.tsv has {len(sample_rows)} rows.")
    if not metadata.get("bioprojects"):
        warnings.append("No BioProject metadata was resolved.")

    lines = [
        "# Sample Count Review",
        "",
        _table(
            ["Source", "Count"],
            [
                ["Paper/supplement reported", paper_count if paper_count not in (None, "") else "Not reported"],
                ["Rows in sample_sheet.tsv", len(sample_rows)],
            ],
        ).rstrip(),
        "",
        "## Public Metadata",
        "",
        _table(["BioProject", "BioSamples", "SRA runs"], project_rows).rstrip(),
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {warning}" for warning in warnings] or ["- No sample count warnings."])
    return "\n".join(lines).rstrip() + "\n"


def build_phenotype_review(mapping_rows: list[dict[str, str]]) -> str:
    problem_rows = [
        row
        for row in mapping_rows
        if row.get("matched_from") == "unmatched" or (row.get("mapping_confidence") or "").lower() == "low"
    ]
    lines = [
        "# Phenotype Mapping Review",
        "",
        f"- Rows in phenotype_mapping.tsv: {len(mapping_rows)}",
        f"- Rows needing review: {len(problem_rows)}",
        "",
        _table(
            ["Sample", "SRA Run", "BioSample", "Group", "Matched From", "Confidence", "Notes"],
            [
                [
                    row.get("sample_name", ""),
                    row.get("sra_run_id", ""),
                    row.get("biosample_accession", ""),
                    row.get("primary_group", ""),
                    row.get("matched_from", ""),
                    row.get("mapping_confidence", ""),
                    row.get("notes", ""),
                ]
                for row in problem_rows[:50]
            ],
        ).rstrip(),
    ]
    return "\n".join(lines).rstrip() + "\n"


def review_packet_node(state: GraphState) -> GraphState:
    packets = dict(state.get("review_packets", {}))
    sample_rows = _read_tsv(Path(state["sample_sheet_path"]))
    mapping_rows = _read_tsv(Path(state["phenotype_mapping_path"]))

    sample_review = _output_path(state, "review_sample_count.md")
    sample_review.write_text(
        build_sample_count_review(state.get("llm_reading", {}), state.get("ncbi_metadata", {}), sample_rows),
        encoding="utf-8",
    )
    packets["sample_count"] = str(sample_review)

    phenotype_review = _output_path(state, "review_phenotype_mapping.md")
    phenotype_review.write_text(build_phenotype_review(mapping_rows), encoding="utf-8")
    packets["phenotype_mapping"] = str(phenotype_review)
    return {"review_packets": packets}


def report_node(state: GraphState) -> GraphState:
    output = _output_path(state, "reanalysis_report.md")
    report = build_reanalysis_report.build_report(
        sample_rows=_read_tsv(Path(state["sample_sheet_path"])),
        mapping_rows=_read_tsv(Path(state["phenotype_mapping_path"])),
        metadata=state.get("ncbi_metadata", {}),
        llm=state.get("llm_reading", {}),
        manifest=state.get("conversion_manifest", {}),
    )
    review_lines = ["", "## Human Review Packets", ""]
    for label, path in sorted(state.get("review_packets", {}).items()):
        review_lines.append(f"- {label}: `{Path(path).name}`")
    output.write_text(report.rstrip() + "\n" + "\n".join(review_lines) + "\n", encoding="utf-8")
    return {"reanalysis_report_path": str(output)}


def persist_state_node(state: GraphState) -> GraphState:
    serializable = dict(state)
    _write_json(_output_path(state, "graph_state.json"), serializable)
    return {}


def _run_sequential(state: GraphState) -> GraphState:
    current: GraphState = dict(state)
    for node in (
        conversion_node,
        regex_accession_node,
        llm_reading_node,
        reconcile_accession_node,
        ncbi_retrieval_node,
        sample_sheet_node,
        phenotype_mapping_node,
        review_packet_node,
        report_node,
        persist_state_node,
    ):
        current.update(node(current))
    return current


def run_workflow(state: GraphState) -> GraphState:
    """Run the workflow with LangGraph when installed, with a sequential fallback for tests."""
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return _run_sequential(state)

    graph = StateGraph(GraphState)
    graph.add_node("convert", conversion_node)
    graph.add_node("extract_regex", regex_accession_node)
    graph.add_node("load_llm", llm_reading_node)
    graph.add_node("reconcile", reconcile_accession_node)
    graph.add_node("retrieve_ncbi", ncbi_retrieval_node)
    graph.add_node("build_sample_sheet", sample_sheet_node)
    graph.add_node("build_phenotype_mapping", phenotype_mapping_node)
    graph.add_node("write_review_packets", review_packet_node)
    graph.add_node("build_report", report_node)
    graph.add_node("persist_state", persist_state_node)

    graph.set_entry_point("convert")
    graph.add_edge("convert", "extract_regex")
    graph.add_edge("extract_regex", "load_llm")
    graph.add_edge("load_llm", "reconcile")
    graph.add_edge("reconcile", "retrieve_ncbi")
    graph.add_edge("retrieve_ncbi", "build_sample_sheet")
    graph.add_edge("build_sample_sheet", "build_phenotype_mapping")
    graph.add_edge("build_phenotype_mapping", "write_review_packets")
    graph.add_edge("write_review_packets", "build_report")
    graph.add_edge("build_report", "persist_state")
    graph.add_edge("persist_state", END)

    return graph.compile().invoke(state)

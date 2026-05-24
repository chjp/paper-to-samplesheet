# Development Guide

Developer reference for the Paper-to-SampleSheet pipeline internals.

## Pipeline Architecture

The LangGraph workflow orchestrates 10 sequential nodes:

```
convert → extract_regex → load_llm → reconcile → retrieve_ncbi
→ build_sample_sheet → build_phenotype_mapping → write_review_packets
→ build_report → persist_state
```

Each node is implemented in a separate module under `src/`.

| Module | Purpose |
| :--- | :--- |
| `convert_documents.py` | Docling-based PDF/DOCX/XLSX → Markdown + JSON conversion |
| `extract_accession_candidates.py` | Regex-based NCBI accession extraction |
| `graph_workflow.py` | LangGraph state graph definition and node functions |
| `retrieve_ncbi.py` | NCBI E-utilities queries (BioProject, BioSample, SRA) |
| `build_sample_sheet.py` | Build the final `sample_sheet.tsv` from NCBI metadata |
| `build_phenotype_mapping.py` | Bridge SRA runs to paper-reported phenotype labels |
| `build_reanalysis_report.py` | Render the Markdown reanalysis report |
| `run_langgraph_workflow.py` | CLI entry point |
| `ensure_env.py` | Virtual environment bootstrap helper |

---

## LLM Reading JSON Schema

If you want to supply an external LLM reading pass (e.g., from your own GPT/Claude pipeline), provide a JSON file matching this schema via `--llm-reading`:

```json
{
  "accessions": [
    {
      "id": "PRJNA...",
      "type": "bioproject|sra_run|sra_experiment|biosample",
      "source_file": "main.md",
      "evidence": "short quote or table row description",
      "confidence": "high|medium|low"
    }
  ],
  "study_metadata": {
    "title": null,
    "sample_count": null,
    "sample_type": null,
    "sequencing_platform": null,
    "target_region": null
  },
  "sample_group_mappings": [],
  "phenotype_mapping_candidates": [
    {
      "paper_sample_id": "sample identifier from paper or supplement",
      "sample_name": null,
      "sra_run_id": null,
      "biosample_accession": null,
      "primary_group": "case/control/treatment/timepoint label",
      "case_control_status": null,
      "disease_or_condition": null,
      "timepoint": null,
      "treatment_group": null,
      "subject_id": null,
      "source_file": "supplement table or converted markdown",
      "evidence": "short quote or table row description",
      "mapping_confidence": "high|medium|low",
      "notes": null
    }
  ],
  "sequencing_protocol": {
    "sequencing_platform": null,
    "library_strategy": null,
    "target_region": null,
    "primers": null,
    "read_layout": null,
    "read_length": null
  },
  "recommended_reanalysis_design": {},
  "data_availability_notes": [],
  "warnings": []
}
```

---

## Sample Sheet TSV Contract

The final `sample_sheet.tsv` has one row per SRA run. Leading columns:

- `sample_name`
- `sra_run_id`
- `biosample_accession`
- `bioproject_id`
- `experiment_accession`
- `platform`
- `library_strategy`
- `library_source`
- `library_selection`

All remaining BioSample attributes are appended as additional columns. Keep this file as clean SRA/BioSample metadata — do not merge uncertain phenotype inference into it.

---

## Phenotype Mapping TSV Contract

`phenotype_mapping.tsv` is the editable bridge between `sample_sheet.tsv` and paper/supplement phenotype labels. One row per `sample_sheet.tsv` row.

Columns:

- `sample_name`
- `sra_run_id`
- `biosample_accession`
- `bioproject_id`
- `paper_sample_id`
- `primary_group`
- `case_control_status`
- `disease_or_condition`
- `timepoint`
- `treatment_group`
- `subject_id`
- `matched_from`
- `mapping_confidence`
- `evidence`
- `notes`

Only per-sample traceable phenotype information belongs here. Study-level interpretation belongs in `reanalysis_report.md`.

---

## Reanalysis Report Sections

`reanalysis_report.md` includes:

- Study Overview
- Public Data Found
- Phenotype Mapping Summary
- Sequencing Details
- Sample Count Audit
- Recommended Reanalysis Design
- Warnings and Open Questions
- Evidence Notes

---

## Supported Accession Types

| Type | Prefixes |
| :--- | :--- |
| BioProject | `PRJNA`, `PRJEB`, `PRJDB` |
| SRA Run | `SRR`, `ERR`, `DRR` |
| SRA Experiment | `SRX`, `ERX`, `DRX` |
| BioSample | `SAMN`, `SAMEA`, `SAMD` |

If only SRR/SRX/SAMN accessions are found, the pipeline resolves them through NCBI rather than requiring a BioProject.

---

## Review Artifacts

The LangGraph workflow generates review artifacts alongside the main outputs:

| File | Purpose |
| :--- | :--- |
| `review_accessions.md` | Regex vs. LLM accession comparison, accepted/rejected IDs, warnings |
| `review_sample_count.md` | Paper-reported count vs. resolved SRA run rows |
| `review_phenotype_mapping.md` | Unmatched or low-confidence phenotype rows flagged for review |
| `graph_state.json` | Full workflow state snapshot for debugging or resumption |

---

## Running Tests

```bash
python3 -m pytest tests -q -p no:cacheprovider
```

Tests use mocks for document conversion and NCBI parsing. No network access required.

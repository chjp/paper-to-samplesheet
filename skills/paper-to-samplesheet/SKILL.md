---
name: paper-to-samplesheet
description: Use when a scientist provides a local folder containing one research paper PDF and supplementary files, and wants Codex to read the materials, find SRA/BioProject/BioSample accessions, retrieve NCBI metadata, and create a generic sample_sheet.tsv. This skill uses Docling for document conversion and a Codex sub-agent for LLM paper reading.
---

# Paper to Sample Sheet

Use this skill for one local paper package at a time. The user should provide or point to a folder containing the main paper PDF and any supplements. Do not ask the scientist to run scripts manually; run the bundled helper scripts yourself and report the final output paths.

The main scientist-facing outputs are `sample_sheet.tsv`, `phenotype_mapping.tsv`, and `reanalysis_report.md`. JSON files are internal/provenance outputs unless the user asks for them.

## Workflow

Use the default script-driven workflow for ordinary requests where the user just wants the final scientist-facing files. Use the LangGraph workflow when the user asks for a reviewable workflow, human-in-the-loop checkpoints, clearer intermediate decisions, resumable execution, or explicitly mentions LangGraph.

### Default Script Workflow

1. Create an output directory named after the input folder under `outputs/`.
2. Ensure the local Python environment is available:
   - Run `scripts/ensure_env.py` from this skill directory when `.venv` is missing or Docling is not importable.
   - It installs `requirements.txt`, including `docling`.
3. Convert paper materials:
   - Run `scripts/convert_documents.py <input-folder> --output <output-folder>/converted`.
   - Use Docling outputs (`.md` and `.json`) as the main reading artifacts.
   - Use spreadsheet TSV previews for supplementary tables.
4. Run deterministic accession discovery:
   - Run `scripts/extract_accession_candidates.py <converted-folder> --output <output-folder>/regex_accessions.json`.
5. Start a Codex sub-agent for the LLM reading pass when the paper text is long, there are multiple supplements, or the regex pass finds no accession with high confidence.
   - Give the sub-agent only converted Markdown/table previews and the schema below.
   - The sub-agent must not call NCBI, mutate files, or create final outputs.
6. Reconcile regex and sub-agent findings:
   - Write `accessions.json` with de-duplicated IDs, evidence, source file, and confidence.
   - Prefer IDs with explicit evidence in the paper or supplement.
   - Keep conflicting or ambiguous IDs in `reanalysis_report.md`.
7. Retrieve NCBI metadata:
   - Run `scripts/retrieve_ncbi.py <accessions.json> --output <output-folder>/ncbi_metadata.json`.
8. Build the final sample sheet:
   - Run `scripts/build_sample_sheet.py <ncbi_metadata.json> --output <output-folder>/sample_sheet.tsv`.
9. Build phenotype mapping:
   - Run `scripts/build_phenotype_mapping.py <sample_sheet.tsv> --llm-reading <llm_reading.json> --output <output-folder>/phenotype_mapping.tsv`.
   - Keep one row per sample sheet row.
   - Use low-confidence `unknown` rows when no per-sample phenotype evidence is available.
10. Write `reanalysis_report.md`:
   - Run `scripts/build_reanalysis_report.py` with sample sheet, phenotype mapping, NCBI metadata, LLM reading, and conversion manifest.
   - Prefer Markdown tables and readable prose over JSON.

### LangGraph Workflow

When LangGraph mode is appropriate, run:

```bash
python scripts/run_langgraph_workflow.py <input-folder> --output <output-folder>
```

Optional inputs:

- `--llm-reading <llm_reading.json>` to import a completed Codex sub-agent reading pass.
- `--ncbi-metadata <ncbi_metadata.json>` to resume from previously retrieved public metadata or avoid a network call during testing/review.

The LangGraph workflow wraps the same helper logic used by the default workflow. It does not change the final scientist-facing output contract:

- `sample_sheet.tsv`
- `phenotype_mapping.tsv`
- `reanalysis_report.md`

It also writes internal/review artifacts:

- `graph_state.json`
- `review_accessions.md`
- `review_sample_count.md`
- `review_phenotype_mapping.md`

Use these review packets for human-in-the-loop discussion. Present them to the scientist as concise review items, not as implementation details.

Generate or call attention to human review when:

- Regex and LLM accession findings disagree.
- No BioProject is found.
- Multiple accession candidates or low-confidence accession candidates are found.
- The paper/supplement reported sample count differs from SRA run rows.
- Phenotype rows are unmatched or low confidence.

After human review, keep the scientist-facing files as the main deliverables. Do not silently overwrite accepted or rejected accession decisions if a future revision adds explicit decision storage.

## Sub-Agent Contract

Ask the sub-agent to return only JSON in this shape:

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

## TSV Contract

The final TSV has one row per SRA run. Leading columns:

- `sample_name`
- `sra_run_id`
- `biosample_accession`
- `bioproject_id`
- `experiment_accession`
- `platform`
- `library_strategy`
- `library_source`
- `library_selection`

Append every BioSample attribute after the leading columns. Keep this file as clean SRA/BioSample metadata; do not merge uncertain LLM phenotype inference into it.

## Phenotype Mapping TSV

`phenotype_mapping.tsv` is the scientist-editable bridge between `sample_sheet.tsv` and the paper/supplement phenotype labels. It has one row per `sample_sheet.tsv` row and includes:

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

Only per-sample traceable phenotype information belongs in this TSV. Study-level interpretation belongs in `reanalysis_report.md`.

## Reanalysis Report

`reanalysis_report.md` is the main human-readable output. Include:

- Study Overview
- Public Data Found
- Phenotype Mapping Summary
- Sequencing Details
- Sample Count Audit
- Recommended Reanalysis Design
- Warnings and Open Questions
- Evidence Notes

## Notes

- Keep the scientist-facing interaction in Codex GUI language: “I converted the files,” “I found these accessions,” “I created the TSV.”
- In final replies, highlight `sample_sheet.tsv`, `phenotype_mapping.tsv`, and `reanalysis_report.md`.
- Helper scripts are internal implementation details.
- NCBI access may fail behind proxies; if it does, preserve `accessions.json` and explain the network blocker in `reanalysis_report.md`.

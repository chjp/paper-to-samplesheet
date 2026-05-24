# 📄 Paper to Sample Sheet

A command-line pipeline that extracts NCBI SRA metadata from local research paper packages and produces standardized sample sheets, phenotype mappings, and reanalysis reports.

Given a folder of paper PDFs and supplementary files, the tool will:
1. Convert documents to Markdown (via [Docling](https://github.com/DS4SD/docling))
2. Extract NCBI accession numbers (BioProject, SRA Run, BioSample, etc.)
3. Resolve full public metadata from NCBI E-utilities
4. Generate a clean `sample_sheet.tsv`, `phenotype_mapping.tsv`, and `reanalysis_report.md`

Orchestrated as a [LangGraph](https://github.com/langchain-ai/langgraph) state graph for transparent, reviewable execution.

---

## 🚀 Quick Start

```bash
# Clone and set up
git clone https://github.com/chjp/paper-to-samplesheet.git
cd paper-to-samplesheet
git checkout langgraph

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the pipeline on a paper folder
python src/run_langgraph_workflow.py paper1/ --output outputs/paper1/
```

---

## 📥 Installation

**Requirements**: Python 3.10+

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or use the bundled environment helper:

```bash
python src/ensure_env.py
```

---

## 🛠️ CLI Usage

```bash
python src/run_langgraph_workflow.py <input_folder> [options]
```

### Arguments

| Argument | Description |
| :--- | :--- |
| `input_folder` | Path to folder containing paper PDF and supplementary files |

### Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `--output <path>` | `outputs/<folder_name>/` | Output directory for all generated files |
| `--llm-reading <path>` | *(none)* | Path to a pre-computed LLM reading JSON (see [DEVELOPMENT.md](DEVELOPMENT.md) for schema) |
| `--ncbi-metadata <path>` | *(none)* | Path to pre-fetched NCBI metadata JSON (skips network calls) |
| `--email <addr>` | `researcher@example.com` | Email for NCBI E-utilities (required by NCBI usage policy) |
| `--api-key <key>` | *(none)* | NCBI API key for higher rate limits |
| `--rate-limit <n>` | `3` | Max NCBI requests per second |

### Examples

```bash
# Basic usage
python src/run_langgraph_workflow.py paper1/

# With custom output directory
python src/run_langgraph_workflow.py paper1/ --output results/my_paper/

# Offline mode (skip NCBI calls, use pre-fetched metadata)
python src/run_langgraph_workflow.py paper1/ --ncbi-metadata cached_metadata.json

# Supply your own LLM-extracted accessions
python src/run_langgraph_workflow.py paper1/ --llm-reading my_llm_output.json

# With NCBI API key for faster queries
python src/run_langgraph_workflow.py paper1/ --email me@uni.edu --api-key ABCDEF123456
```

---

## 📊 Pipeline Steps

The workflow executes 10 sequential graph nodes:

```
┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌───────────┐   ┌──────────────┐
│ convert  │──▶│ extract_regex│──▶│ load_llm │──▶│ reconcile │──▶│ retrieve_ncbi│
└──────────┘   └──────────────┘   └──────────┘   └───────────┘   └──────────────┘
                                                                         │
     ┌───────────────────────────────────────────────────────────────────┘
     ▼
┌──────────────────┐   ┌────────────────────────┐   ┌──────────────────────┐
│ build_sample_sheet│──▶│ build_phenotype_mapping│──▶│ write_review_packets │
└──────────────────┘   └────────────────────────┘   └──────────────────────┘
                                                              │
     ┌────────────────────────────────────────────────────────┘
     ▼
┌──────────────┐   ┌───────────────┐
│ build_report │──▶│ persist_state │
└──────────────┘   └───────────────┘
```

| Step | Description |
| :--- | :--- |
| **convert** | Converts PDFs, DOCX, XLSX into Markdown and TSV previews using Docling |
| **extract_regex** | Scans converted text for NCBI accession patterns (PRJNA, SRR, SAMN, etc.) |
| **load_llm** | Loads external LLM reading JSON if provided via `--llm-reading` |
| **reconcile** | Merges regex and LLM accession findings, deduplicates, assigns confidence |
| **retrieve_ncbi** | Queries NCBI E-utilities to resolve BioProjects → BioSamples → SRA runs |
| **build_sample_sheet** | Writes `sample_sheet.tsv` with one row per SRA run |
| **build_phenotype_mapping** | Links SRA runs to paper-reported experimental groups |
| **write_review_packets** | Generates human-reviewable Markdown summaries for QC |
| **build_report** | Compiles `reanalysis_report.md` |
| **persist_state** | Saves `graph_state.json` for debugging and resumption |

---

## 📁 Output Files

All outputs are written to `outputs/<paper_folder_name>/` (or your `--output` path):

### Primary Outputs

| File | Description |
| :--- | :--- |
| `sample_sheet.tsv` | Standardized SRA run-level metadata (platform, library strategy, BioSample attributes) |
| `phenotype_mapping.tsv` | Editable mapping of SRA runs to paper-reported groups, treatments, timepoints |
| `reanalysis_report.md` | Human-readable summary: study overview, data audit, sequencing details, reanalysis design |

### Review Artifacts

| File | Description |
| :--- | :--- |
| `review_accessions.md` | Regex vs. LLM accession comparison, accepted/rejected IDs |
| `review_sample_count.md` | Paper-reported sample count vs. resolved SRA rows |
| `review_phenotype_mapping.md` | Flagged unmatched or low-confidence phenotype rows |
| `graph_state.json` | Full workflow state snapshot |

### Intermediate Files

| File | Description |
| :--- | :--- |
| `converted/` | Markdown and JSON artifacts from document conversion |
| `regex_accessions.json` | Raw regex extraction results |
| `accessions.json` | Reconciled accession list |
| `ncbi_metadata.json` | Full NCBI response data |
| `llm_reading.json` | LLM reading pass output (imported or empty) |

---

## 🧪 Running Tests

```bash
python3 -m pytest tests -q -p no:cacheprovider
```

Tests use mocks for document conversion and NCBI API calls. No network access required.

---

## 📂 Project Structure

```
paper-to-samplesheet/
├── src/                          # Pipeline source code
│   ├── run_langgraph_workflow.py  # CLI entry point
│   ├── graph_workflow.py          # LangGraph state graph + node functions
│   ├── convert_documents.py       # Docling document conversion
│   ├── extract_accession_candidates.py  # Regex accession extraction
│   ├── retrieve_ncbi.py           # NCBI E-utilities queries
│   ├── build_sample_sheet.py      # Sample sheet TSV builder
│   ├── build_phenotype_mapping.py # Phenotype mapping builder
│   ├── build_reanalysis_report.py # Markdown report generator
│   └── ensure_env.py             # Environment bootstrap helper
├── tests/                        # Unit tests (pytest)
├── requirements.txt              # Python dependencies
├── DEVELOPMENT.md                # Developer reference (schemas, contracts)
└── README.md                     # This file
```

---

## 🚫 Out of Scope

This tool extracts metadata only. It does **not**:

1. Download raw sequencing FASTQ files
2. Search PubMed or screen abstracts
3. Download PDFs from PMC (you supply local files)
4. Run downstream bioinformatics pipelines (alignment, assembly, DE analysis)

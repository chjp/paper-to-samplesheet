# 📄 Paper to Sample Sheet

An intelligent, Codex-powered GUI agentic workflow designed to transform local scientific research paper packages into standardized NCBI SRA (Sequence Read Archive) sample sheets, phenotype mappings, and reanalysis plans.

No command-line expertise required. Simply point **ChatGPT Codex Desktop App** to this folder and let the agent do the heavy lifting.

---

## 🌟 Key Features

* **📄 Intelligent Document Conversion**: Powered by **Docling** to automatically convert PDFs, DOCX files, spreadsheets (XLSX, CSV, TSV), and supplementary materials into clean Markdown and preview tables.
* **🔍 Hybrid Accession Discovery**: Combines deterministic regular expressions (high precision) with a **Codex LLM sub-agent** (high semantic understanding) to extract NCBI accession IDs (BioProject, SRA Run, SRA Experiment, BioSample).
* **🧬 NCBI E-Utilities Integration**: Automatically resolves and retrieves complete public metadata from NCBI databases, linking BioProjects to BioSamples and SRA runs.
* **📊 Scientist-Editable Phenotype Mapping**: Creates a seamless bridge (`phenotype_mapping.tsv`) linking base SRA sequence runs to the specific experimental groups, treatments, or timepoints reported in the paper.
* **✍️ Plan Reanalysis Automatically**: Generates a comprehensive reanalysis report (`reanalysis_report.md`) detailing study overviews, public data audits, sequencing strategies, and recommended downstream bioinformatics designs.

---

## 🛠️ How to Use in ChatGPT Codex Desktop App

This workflow is optimized for the **ChatGPT Codex Desktop App** GUI interface. Scientists do not need to run command-line scripts manually.

```
┌────────────────────────────────────────────────────────┐
│               1. Create Paper Folder                   │
│  Put paper.pdf + supplement.xlsx into `paper_name/`    │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│               2. Open Codex Desktop                   │
│  Open this repository as a project in Codex            │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│               3. Tell Codex to Start                   │
│  "Process `paper_name/` and create sample sheet"       │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│               4. Codex Agent Runs                      │
│  Converts docs ➔ Finds IDs ➔ NCBI ➔ Phenotypes ➔ Report│
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│              5. Scientist Outputs                      │
│  • sample_sheet.tsv      • phenotype_mapping.tsv       │
│                  • reanalysis_report.md                │
└────────────────────────────────────────────────────────┘
```

### Step 1: Create a Paper Folder
Unzip or clone this repository, and create a new subfolder (e.g., `paper1/`) anywhere inside it. Place all resources for the paper you want to analyze in that folder:
* Main paper PDF
* Supplementary PDF documents
* Word documents (`.docx`)
* Supplementary tables (`.xlsx`, `.csv`, `.tsv`)

### Step 2: Open in Codex Desktop App
Open the **ChatGPT Codex Desktop App** and create a new project pointing to the root directory of this repository.

### Step 3: Run the Agent
Simply ask Codex in the chat:
> *"Please analyze the paper and supplementary materials under `paper1/` and generate a sample sheet."*

### Step 4: Codex Workflow Execution
Codex will automatically invoke the core skill and run the helper tools under the hood:
1. **Environment Setup**: Automatically configures the local Python environment and imports dependencies.
2. **Doc Conversion**: Parses your PDFs/spreadsheets into highly readable markdown formats.
3. **Accession Search**: Identifies `PRJNA`, `SRR`, `SRX`, `SAMN` and other public accessions from the text and tables.
4. **NCBI Query**: Fetches the official BioProject, BioSample, and run metadata from NCBI.
5. **Phenotype Extraction**: Extracts sample metadata, treatment conditions, and experimental groups.
6. **Report Compilation**: Integrates all data into final output files.

---

## 📁 Main Output Files

The workflow generates the following outputs in your project folder under `outputs/{paper_folder_name}/`:

| Filename | Purpose | Description |
| :--- | :--- | :--- |
| **`sample_sheet.tsv`** | **SRA Metadata** | A clean, standardized SRA run-level metadata sheet. Contains sequencing platform, library strategy, selection, and all official NCBI BioSample attributes as columns. |
| **`phenotype_mapping.tsv`** | **Phenotype Bridge** | A scientist-editable table linking the raw `sra_run_id` to paper-specific sample IDs, treatment groups, disease status, timepoints, and confidence levels. |
| **`reanalysis_report.md`** | **Human Report** | A clean markdown document summarizing the study overview, dataset audits, library protocols, recommended reanalysis designs, and open warnings/questions. |

> [!TIP]
> Scientists can easily open `phenotype_mapping.tsv` in Microsoft Excel, verify or edit the mappings manually, and then join it with `sample_sheet.tsv` for downstream RNA-Seq/Metagenomics analysis.


## 🚫 Design Boundaries & Out of Scope
To maintain a focused and reliable tool, this agent does **not**:
1. Download large raw sequencing FASTQ files.
2. Automate PubMed search or abstract screening.
3. Automatically download PDFs from PMC (you must supply local files).
4. Run downstream alignment, assembly, or differential expression pipelines.

import json

import graph_workflow


def test_initial_state_defaults_to_outputs_folder(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_folder = tmp_path / "paper1"
    input_folder.mkdir()

    state = graph_workflow.initial_state(input_folder)

    assert state["input_folder"] == str(input_folder.resolve())
    assert state["output_folder"] == str((tmp_path / "outputs" / "paper1").resolve())
    assert state["converted_folder"].endswith("outputs/paper1/converted")
    assert state["review_packets"] == {}


def test_reconcile_node_reuses_existing_accession_merge(tmp_path):
    state = {
        "output_folder": str(tmp_path),
        "regex_accessions": {
            "accessions": [
                {
                    "id": "prjna1",
                    "type": "bioproject",
                    "source_file": "main.md",
                    "evidence": "Data PRJNA1",
                    "confidence": "high",
                }
            ]
        },
        "llm_reading": {
            "accessions": [
                {
                    "id": "SRR1",
                    "type": "run",
                    "source_file": "supp.md",
                    "evidence": "run table",
                    "confidence": "medium",
                }
            ]
        },
        "review_packets": {},
    }

    result = graph_workflow.reconcile_accession_node(state)

    ids = {row["id"] for row in result["accessions"]["accessions"]}
    assert ids == {"PRJNA1", "SRR1"}
    assert (tmp_path / "accessions.json").exists()
    assert "review_accessions.md" in result["review_packets"]["accessions"]


def test_sample_mapping_report_nodes_write_outputs(tmp_path):
    state = {
        "output_folder": str(tmp_path),
        "ncbi_metadata": {
            "bioprojects": [
                {
                    "bioproject_id": "PRJNA1",
                    "biosample_count": 1,
                    "sra_run_count": 1,
                    "biosamples": [
                        {
                            "accession": "SAMN1",
                            "attributes": {"sample_name": "S1"},
                        }
                    ],
                    "sra_runs": [
                        {
                            "run_accession": "SRR1",
                            "biosample_accession": "SAMN1",
                            "bioproject_id": "PRJNA1",
                            "experiment_accession": "SRX1",
                            "platform": "ILLUMINA",
                            "library_strategy": "AMPLICON",
                        }
                    ],
                }
            ],
            "unresolved": [],
        },
        "llm_reading": {
            "study_metadata": {"sample_count": 2},
            "phenotype_mapping_candidates": [
                {
                    "sra_run_id": "SRR1",
                    "paper_sample_id": "P1",
                    "primary_group": "case",
                    "mapping_confidence": "high",
                    "evidence": "supp table",
                }
            ],
        },
        "conversion_manifest": {"files": []},
        "review_packets": {},
    }

    state.update(graph_workflow.sample_sheet_node(state))
    state.update(graph_workflow.phenotype_mapping_node(state))
    state.update(graph_workflow.review_packet_node(state))
    state.update(graph_workflow.report_node(state))
    state.update(graph_workflow.persist_state_node(state))

    assert (tmp_path / "sample_sheet.tsv").exists()
    assert (tmp_path / "phenotype_mapping.tsv").exists()
    assert (tmp_path / "review_sample_count.md").read_text(encoding="utf-8").count("Paper reports 2 samples") == 1
    report = (tmp_path / "reanalysis_report.md").read_text(encoding="utf-8")
    assert "Human Review Packets" in report
    assert "review_phenotype_mapping.md" in report
    graph_state = json.loads((tmp_path / "graph_state.json").read_text(encoding="utf-8"))
    assert graph_state["sample_sheet_path"].endswith("sample_sheet.tsv")


def test_review_packets_cover_missing_bioproject_and_low_confidence():
    accession_review = graph_workflow.build_accession_review(
        {"accessions": [{"id": "SRR1", "type": "sra_run", "confidence": "low"}]},
        {"accessions": []},
        {"accessions": [{"id": "SRR1", "type": "sra_run", "sources": ["regex"], "confidence": "low"}]},
    )
    phenotype_review = graph_workflow.build_phenotype_review(
        [
            {
                "sample_name": "S1",
                "sra_run_id": "SRR1",
                "biosample_accession": "SAMN1",
                "primary_group": "unknown",
                "matched_from": "unmatched",
                "mapping_confidence": "low",
            }
        ]
    )

    assert "No BioProject accession" in accession_review
    assert "low confidence" in accession_review
    assert "Rows needing review: 1" in phenotype_review

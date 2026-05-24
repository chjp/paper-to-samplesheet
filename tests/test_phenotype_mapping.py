import csv
import json

import build_phenotype_mapping


def test_mapping_has_one_row_per_sample_sheet_row():
    sample_rows = [
        {
            "sample_name": "S1",
            "sra_run_id": "SRR1",
            "biosample_accession": "SAMN1",
            "bioproject_id": "PRJNA1",
        },
        {
            "sample_name": "S2",
            "sra_run_id": "SRR2",
            "biosample_accession": "SAMN2",
            "bioproject_id": "PRJNA1",
        },
    ]
    rows = build_phenotype_mapping.build_mapping(sample_rows, [])

    assert len(rows) == 2
    assert rows[0]["primary_group"] == "unknown"
    assert rows[0]["mapping_confidence"] == "low"
    assert rows[0]["matched_from"] == "unmatched"


def test_match_priority_prefers_sra_run_over_biosample():
    row = {
        "sample_name": "SampleA",
        "sra_run_id": "SRR1",
        "biosample_accession": "SAMN1",
        "bioproject_id": "PRJNA1",
    }
    candidates = [
        {
            "biosample_accession": "SAMN1",
            "primary_group": "control",
            "mapping_confidence": "medium",
        },
        {
            "sra_run_id": "SRR1",
            "primary_group": "case",
            "mapping_confidence": "high",
        },
    ]

    candidate, matched_from = build_phenotype_mapping.match_candidate(row, candidates)

    assert matched_from == "sra_run_id"
    assert candidate["primary_group"] == "case"


def test_paper_sample_id_can_match_biosample_attribute():
    row = {
        "sample_name": "NCBI name",
        "sra_run_id": "SRR1",
        "biosample_accession": "SAMN1",
        "bioproject_id": "PRJNA1",
        "host_subject_id": "P001",
    }
    candidates = [
        {
            "paper_sample_id": "P001",
            "primary_group": "treated",
            "mapping_confidence": "high",
        }
    ]

    candidate, matched_from = build_phenotype_mapping.match_candidate(row, candidates)

    assert matched_from == "biosample_attribute"
    assert candidate["primary_group"] == "treated"


def test_write_mapping_tsv_round_trips(tmp_path):
    output = tmp_path / "phenotype_mapping.tsv"
    rows = [
        {
            "sample_name": "S1",
            "sra_run_id": "SRR1",
            "biosample_accession": "SAMN1",
            "bioproject_id": "PRJNA1",
            "primary_group": "case",
            "mapping_confidence": "high",
        }
    ]

    build_phenotype_mapping.write_mapping(rows, output)

    with output.open(encoding="utf-8") as handle:
        parsed = list(csv.DictReader(handle, delimiter="\t"))
    assert parsed[0]["sra_run_id"] == "SRR1"
    assert parsed[0]["primary_group"] == "case"

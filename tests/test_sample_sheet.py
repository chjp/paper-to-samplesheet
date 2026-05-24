import csv
import json

import build_sample_sheet


def test_rows_from_metadata_preserves_biosample_attributes():
    metadata = {
        "bioprojects": [
            {
                "bioproject_id": "PRJNA613586",
                "biosamples": [
                    {
                        "accession": "SAMN14407001",
                        "attributes": {"sample_name": "T54", "host": "Homo sapiens"},
                    }
                ],
                "sra_runs": [
                    {
                        "run_accession": "SRR11355982",
                        "biosample_accession": "SAMN14407001",
                        "bioproject_id": "PRJNA613586",
                        "experiment_accession": "SRX001",
                        "platform": "ILLUMINA",
                        "library_strategy": "AMPLICON",
                    }
                ],
            }
        ],
        "unresolved": [],
    }

    rows = build_sample_sheet.rows_from_metadata(metadata)

    assert rows[0]["sample_name"] == "T54"
    assert rows[0]["host"] == "Homo sapiens"


def test_write_tsv_is_tab_delimited(tmp_path):
    rows = [
        {
            "sample_name": "T54",
            "sra_run_id": "SRR11355982",
            "biosample_accession": "SAMN14407001",
            "bioproject_id": "PRJNA613586",
            "host": "Homo sapiens",
        }
    ]
    output = tmp_path / "sample_sheet.tsv"

    build_sample_sheet.write_tsv(rows, output)

    text = output.read_text(encoding="utf-8")
    assert "\t" in text.splitlines()[0]
    with output.open(encoding="utf-8") as handle:
        parsed = list(csv.DictReader(handle, delimiter="\t"))
    assert parsed[0]["host"] == "Homo sapiens"


def test_report_mentions_unresolved():
    metadata = {"bioprojects": [], "unresolved": [{"id": "SRR0", "type": "sra_run", "reason": "not found"}]}
    report = build_sample_sheet.report_markdown(metadata, [])

    assert "Unresolved accessions: 1" in report
    assert "`SRR0`" in report

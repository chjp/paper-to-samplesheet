import json

import extract_accession_candidates as accessions


def test_scan_text_finds_supported_accessions():
    text = "Raw reads are under PRJNA613586. Runs include SRR11355982 and BioSample SAMN14407001."
    results = accessions.scan_text(text, "main.md")

    found = {(r.id, r.type) for r in results}
    assert ("PRJNA613586", "bioproject") in found
    assert ("SRR11355982", "sra_run") in found
    assert ("SAMN14407001", "biosample") in found


def test_scan_folder_deduplicates_by_source(tmp_path):
    converted = tmp_path / "converted"
    converted.mkdir()
    (converted / "main.md").write_text("PRJNA613586 PRJNA613586", encoding="utf-8")

    results = accessions.scan_folder(converted)

    assert len(results) == 1
    assert results[0]["id"] == "PRJNA613586"


def test_reconcile_merges_regex_and_llm_results():
    regex_results = [
        {
            "id": "prjna613586",
            "type": "bioproject",
            "source_file": "main.md",
            "evidence": "Data: PRJNA613586",
            "confidence": "high",
        }
    ]
    llm_results = [
        {
            "id": "PRJNA613586",
            "type": "project",
            "source_file": "supp.md",
            "evidence": "NCBI BioProject PRJNA613586",
            "confidence": "medium",
        },
        {
            "id": "SRR11355982",
            "type": "run",
            "source_file": "supp.md",
            "evidence": "run table",
            "confidence": "high",
        },
    ]

    merged = accessions.reconcile_accessions(regex_results, llm_results)

    assert len(merged["accessions"]) == 2
    project = next(r for r in merged["accessions"] if r["id"] == "PRJNA613586")
    assert project["sources"] == ["regex", "llm"]
    assert project["confidence"] == "high"

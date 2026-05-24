import build_reanalysis_report


def test_report_contains_scientist_readable_sections():
    sample_rows = [
        {
            "sample_name": "S1",
            "sra_run_id": "SRR1",
            "biosample_accession": "SAMN1",
            "bioproject_id": "PRJNA1",
            "platform": "ILLUMINA",
            "library_strategy": "AMPLICON",
        }
    ]
    mapping_rows = [
        {
            "sample_name": "S1",
            "sra_run_id": "SRR1",
            "biosample_accession": "SAMN1",
            "bioproject_id": "PRJNA1",
            "primary_group": "case",
            "mapping_confidence": "high",
            "matched_from": "sra_run_id",
            "evidence": "Supplement table labels S1 as case.",
        }
    ]
    metadata = {
        "bioprojects": [
            {
                "bioproject_id": "PRJNA1",
                "biosample_count": 1,
                "sra_run_count": 1,
            }
        ],
        "unresolved": [],
    }
    llm = {
        "study_metadata": {
            "title": "Example study",
            "sample_count": 1,
            "sample_type": "saliva",
            "study_design": "case-control",
        },
        "sequencing_protocol": {"target_region": "V3-V4"},
    }

    report = build_reanalysis_report.build_report(sample_rows, mapping_rows, metadata, llm)

    assert "# Reanalysis Report" in report
    assert "## Phenotype Mapping Summary" in report
    assert "## Sample Count Audit" in report
    assert "phenotype_mapping.tsv" in report
    assert "| case | 1 |" in report


def test_report_warns_about_low_confidence_and_mismatch():
    sample_rows = [{"sample_name": "S1", "sra_run_id": "SRR1"}]
    mapping_rows = [
        {
            "sample_name": "S1",
            "sra_run_id": "SRR1",
            "primary_group": "unknown",
            "mapping_confidence": "low",
            "matched_from": "unmatched",
        }
    ]
    metadata = {"bioprojects": [], "unresolved": [{"id": "SRR0", "reason": "not found"}]}
    llm = {"study_metadata": {"sample_count": 2}}

    report = build_reanalysis_report.build_report(sample_rows, mapping_rows, metadata, llm)

    assert "low-confidence mappings" in report
    assert "could not be matched" in report
    assert "Paper reports 2 samples" in report
    assert "Unresolved accession `SRR0`" in report

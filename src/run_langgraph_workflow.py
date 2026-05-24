#!/usr/bin/env python3
"""Run the LangGraph paper-to-samplesheet workflow."""

from __future__ import annotations

import argparse
from pathlib import Path

from graph_workflow import initial_state, run_workflow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_folder", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--llm-reading", type=Path, default=None)
    parser.add_argument("--ncbi-metadata", type=Path, default=None)
    parser.add_argument("--email", default="researcher@example.com")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--rate-limit", type=int, default=3)
    args = parser.parse_args()

    state = initial_state(
        args.input_folder,
        args.output,
        llm_reading_path=args.llm_reading,
        ncbi_metadata_path=args.ncbi_metadata,
        email=args.email,
        api_key=args.api_key,
        rate_limit=args.rate_limit,
    )
    final_state = run_workflow(state)
    print(final_state["reanalysis_report_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

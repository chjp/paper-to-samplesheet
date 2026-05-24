#!/usr/bin/env python3
"""Convert paper PDFs and supplements into Codex-readable artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DOCLING_SUFFIXES = {
    ".pdf",
    ".docx",
    ".pptx",
    ".html",
    ".htm",
    ".xlsx",
    ".csv",
    ".md",
    ".txt",
}
SPREADSHEET_SUFFIXES = {".xlsx", ".xls", ".csv", ".tsv"}


def _safe_stem(path: Path) -> str:
    return path.name.replace("/", "_").replace(" ", "_")


def _json_default(value: Any) -> str:
    return str(value)


def convert_with_docling(path: Path, output_dir: Path) -> dict:
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(path))
    document = result.document

    base = _safe_stem(path)
    md_path = output_dir / f"{base}.md"
    json_path = output_dir / f"{base}.docling.json"

    md_path.write_text(document.export_to_markdown(), encoding="utf-8")
    json_path.write_text(
        json.dumps(document.export_to_dict(), indent=2, default=_json_default),
        encoding="utf-8",
    )

    return {
        "file": str(path),
        "markdown": str(md_path),
        "json": str(json_path),
        "status": "converted",
        "warnings": [],
    }


def convert_plain_text(path: Path, output_dir: Path) -> dict:
    base = _safe_stem(path)
    md_path = output_dir / f"{base}.md"
    md_path.write_text(path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    return {
        "file": str(path),
        "markdown": str(md_path),
        "json": None,
        "status": "copied",
        "warnings": [],
    }


def write_spreadsheet_previews(path: Path, output_dir: Path) -> list[dict]:
    import pandas as pd

    previews: list[dict] = []
    base = _safe_stem(path)
    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xls"}:
        sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
        for sheet_name, df in sheets.items():
            preview_path = output_dir / f"{base}.{sheet_name}.preview.tsv"
            df.to_csv(preview_path, sep="\t", index=False)
            previews.append(
                {
                    "sheet": sheet_name,
                    "rows": int(len(df)),
                    "columns": list(map(str, df.columns)),
                    "preview_tsv": str(preview_path),
                }
            )
    else:
        sep = "\t" if suffix == ".tsv" else ","
        df = pd.read_csv(path, sep=sep)
        preview_path = output_dir / f"{base}.preview.tsv"
        df.to_csv(preview_path, sep="\t", index=False)
        previews.append(
            {
                "sheet": None,
                "rows": int(len(df)),
                "columns": list(map(str, df.columns)),
                "preview_tsv": str(preview_path),
            }
        )

    return previews


def convert_folder(input_folder: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"input_folder": str(input_folder), "files": []}

    for path in sorted(input_folder.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in DOCLING_SUFFIXES and suffix not in SPREADSHEET_SUFFIXES:
            manifest["files"].append(
                {
                    "file": str(path),
                    "status": "skipped",
                    "warnings": [f"Unsupported file suffix: {suffix}"],
                }
            )
            continue

        try:
            if suffix in {".md", ".txt"}:
                entry = convert_plain_text(path, output_dir)
            else:
                entry = convert_with_docling(path, output_dir)
        except Exception as exc:
            entry = {
                "file": str(path),
                "markdown": None,
                "json": None,
                "status": "conversion_failed",
                "warnings": [str(exc)],
            }

        if suffix in SPREADSHEET_SUFFIXES:
            try:
                entry["spreadsheet_previews"] = write_spreadsheet_previews(path, output_dir)
            except Exception as exc:
                entry.setdefault("warnings", []).append(f"Spreadsheet preview failed: {exc}")

        manifest["files"].append(entry)

    manifest_path = output_dir / "conversion_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_folder", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = convert_folder(args.input_folder.resolve(), args.output.resolve())
    print(args.output / "conversion_manifest.json")
    return 0 if any(f["status"] in {"converted", "copied"} for f in manifest["files"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())

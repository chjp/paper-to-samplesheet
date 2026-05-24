#!/usr/bin/env python3
"""Resolve NCBI accessions into BioSample attributes and SRA runs."""

from __future__ import annotations

import argparse
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from Bio import Entrez


class RateLimiter:
    def __init__(self, requests_per_second: int = 3):
        self.interval = 1.0 / requests_per_second
        self.last_call = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_call
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.monotonic()


def parse_biosample_xml(xml_data: bytes | str) -> list[dict]:
    if isinstance(xml_data, bytes):
        xml_data = xml_data.decode("utf-8")
    root = ET.fromstring(xml_data)
    biosamples = []
    for bs_elem in root.findall(".//BioSample"):
        accession = bs_elem.get("accession", "")
        bs_id_elem = bs_elem.find(".//Id[@db='BioSample']")
        attributes = {}
        for attr in bs_elem.findall(".//Attribute"):
            name = attr.get("attribute_name", attr.get("harmonized_name", "unknown"))
            attributes[name] = attr.text.strip() if attr.text else ""
        biosamples.append(
            {
                "biosample_id": bs_id_elem.text if bs_id_elem is not None else accession,
                "accession": accession,
                "attributes": attributes,
            }
        )
    return biosamples


def parse_sra_xml(xml_data: bytes | str) -> list[dict]:
    if isinstance(xml_data, bytes):
        xml_data = xml_data.decode("utf-8")
    try:
        root = ET.fromstring(f"<root>{xml_data}</root>")
    except ET.ParseError:
        root = ET.fromstring(xml_data)

    runs = []
    for pkg in root.iter("EXPERIMENT_PACKAGE"):
        exp_elem = pkg.find(".//EXPERIMENT")
        exp_acc = exp_elem.get("accession", "") if exp_elem is not None else ""
        platform = ""
        platform_elem = pkg.find(".//PLATFORM")
        if platform_elem is not None and len(platform_elem) > 0:
            platform = platform_elem[0].tag

        def text_at(tag: str) -> str:
            elem = pkg.find(f".//{tag}")
            return elem.text.strip() if elem is not None and elem.text else ""

        biosample_acc = ""
        bioproject_id = ""
        for ext_id in pkg.iter("EXTERNAL_ID"):
            namespace = (ext_id.get("namespace") or "").lower()
            if namespace == "biosample":
                biosample_acc = ext_id.text or ""
            elif namespace == "bioproject":
                bioproject_id = ext_id.text or ""
        if not biosample_acc:
            sample_elem = pkg.find(".//SAMPLE")
            if sample_elem is not None:
                biosample_acc = sample_elem.get("accession", "")

        for run_elem in pkg.iter("RUN"):
            run_acc = run_elem.get("accession", "")
            if run_acc:
                runs.append(
                    {
                        "run_accession": run_acc,
                        "biosample_accession": biosample_acc,
                        "bioproject_id": bioproject_id,
                        "experiment_accession": exp_acc,
                        "platform": platform,
                        "library_strategy": text_at("LIBRARY_STRATEGY"),
                        "library_source": text_at("LIBRARY_SOURCE"),
                        "library_selection": text_at("LIBRARY_SELECTION"),
                    }
                )
    return runs


def fetch_biosamples_by_uids(uids: list[str], limiter: RateLimiter) -> list[dict]:
    if not uids:
        return []
    limiter.wait()
    handle = Entrez.efetch(db="biosample", id=uids, rettype="full", retmode="xml")
    data = handle.read()
    handle.close()
    return parse_biosample_xml(data)


def fetch_sra_by_uids(uids: list[str], limiter: RateLimiter) -> list[dict]:
    if not uids:
        return []
    limiter.wait()
    handle = Entrez.efetch(db="sra", id=uids, rettype="full", retmode="xml")
    data = handle.read()
    handle.close()
    return parse_sra_xml(data)


def search_uids(db: str, term: str, limiter: RateLimiter, retmax: int = 10000) -> list[str]:
    limiter.wait()
    handle = Entrez.esearch(db=db, term=term, retmax=retmax)
    result = Entrez.read(handle)
    handle.close()
    return result.get("IdList", [])


def linked_uids(dbfrom: str, db: str, uid: str, limiter: RateLimiter) -> list[str]:
    limiter.wait()
    handle = Entrez.elink(dbfrom=dbfrom, db=db, id=uid)
    result = Entrez.read(handle)
    handle.close()
    uids = []
    if result and result[0].get("LinkSetDb"):
        for link_set in result[0]["LinkSetDb"]:
            for link in link_set.get("Link", []):
                uids.append(link["Id"])
    return uids


def bioproject_accession_from_uid(uid: str, limiter: RateLimiter) -> str:
    limiter.wait()
    handle = Entrez.efetch(db="bioproject", id=uid, rettype="xml")
    xml_data = handle.read()
    handle.close()
    if isinstance(xml_data, bytes):
        xml_data = xml_data.decode("utf-8")
    match = re.search(r'<ArchiveID id="([^"]+)"', xml_data)
    return match.group(1) if match else uid


def resolve_bioproject(accession: str, limiter: RateLimiter) -> dict:
    bp_uids = search_uids("bioproject", accession, limiter, retmax=10)
    if not bp_uids:
        return {"bioproject_id": accession, "biosamples": [], "sra_runs": [], "warnings": ["BioProject not found"]}
    bp_uid = bp_uids[0]
    bs_uids = linked_uids("bioproject", "biosample", bp_uid, limiter)
    biosamples = fetch_biosamples_by_uids(bs_uids, limiter)
    sra_uids = search_uids("sra", accession, limiter)
    sra_runs = fetch_sra_by_uids(sra_uids, limiter)
    for run in sra_runs:
        run["bioproject_id"] = run.get("bioproject_id") or accession
    return {"bioproject_id": accession, "biosamples": biosamples, "sra_runs": sra_runs, "warnings": []}


def resolve_sra(term: str, limiter: RateLimiter) -> dict:
    sra_uids = search_uids("sra", term, limiter, retmax=100)
    sra_runs = fetch_sra_by_uids(sra_uids, limiter)
    biosample_ids = sorted({r["biosample_accession"] for r in sra_runs if r.get("biosample_accession")})
    biosamples = []
    for accession in biosample_ids:
        bs_uids = search_uids("biosample", accession, limiter, retmax=10)
        biosamples.extend(fetch_biosamples_by_uids(bs_uids, limiter))
    bp_ids = sorted({r["bioproject_id"] for r in sra_runs if r.get("bioproject_id")})
    return {"bioproject_id": bp_ids[0] if bp_ids else "", "biosamples": biosamples, "sra_runs": sra_runs, "warnings": []}


def resolve_biosample(accession: str, limiter: RateLimiter) -> dict:
    bs_uids = search_uids("biosample", accession, limiter, retmax=10)
    biosamples = fetch_biosamples_by_uids(bs_uids, limiter)
    sra_uids = []
    for uid in bs_uids:
        sra_uids.extend(linked_uids("biosample", "sra", uid, limiter))
    sra_runs = fetch_sra_by_uids(sra_uids, limiter)
    bp_ids = sorted({r["bioproject_id"] for r in sra_runs if r.get("bioproject_id")})
    return {"bioproject_id": bp_ids[0] if bp_ids else "", "biosamples": biosamples, "sra_runs": sra_runs, "warnings": []}


def resolve_accessions(accessions: list[dict], email: str, api_key: str | None = None, rate_limit: int = 3) -> dict:
    Entrez.email = email
    if api_key:
        Entrez.api_key = api_key
    limiter = RateLimiter(rate_limit)
    projects: dict[str, dict] = {}
    unresolved = []

    for accession in accessions:
        acc_id = accession["id"]
        acc_type = accession["type"]
        try:
            if acc_type == "bioproject":
                record = resolve_bioproject(acc_id, limiter)
            elif acc_type in {"sra_run", "sra_experiment"}:
                record = resolve_sra(acc_id, limiter)
            elif acc_type == "biosample":
                record = resolve_biosample(acc_id, limiter)
            else:
                unresolved.append({**accession, "reason": "unsupported accession type"})
                continue
        except Exception as exc:
            unresolved.append({**accession, "reason": str(exc)})
            continue

        bp_id = record.get("bioproject_id") or f"unresolved:{acc_id}"
        project = projects.setdefault(
            bp_id,
            {"bioproject_id": bp_id, "biosamples": [], "sra_runs": [], "warnings": []},
        )
        project["biosamples"].extend(record.get("biosamples", []))
        project["sra_runs"].extend(record.get("sra_runs", []))
        project["warnings"].extend(record.get("warnings", []))

    return {
        "bioprojects": [_dedupe_project(p) for p in projects.values()],
        "unresolved": unresolved,
    }


def _dedupe_project(project: dict) -> dict:
    biosamples = {b.get("accession") or b.get("biosample_id"): b for b in project["biosamples"]}
    runs = {r.get("run_accession"): r for r in project["sra_runs"]}
    project["biosamples"] = [v for k, v in biosamples.items() if k]
    project["sra_runs"] = [v for k, v in runs.items() if k]
    project["biosample_count"] = len(project["biosamples"])
    project["sra_run_count"] = len(project["sra_runs"])
    return project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("accessions_json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--email", default="researcher@example.com")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--rate-limit", type=int, default=3)
    args = parser.parse_args()

    data = json.loads(args.accessions_json.read_text(encoding="utf-8"))
    metadata = resolve_accessions(data.get("accessions", []), args.email, args.api_key, args.rate_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

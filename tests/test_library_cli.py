from __future__ import annotations

import json
import subprocess

from conftest import ROOT
from paper_engine.candidates import append_candidates, load_candidates
from paper_engine.citation_guard import check_bib
from paper_engine.topic import init_topic


def _write_library(root):
    (root / "library.bib").write_text(
        "\n".join(
            [
                "@article{Alpha2024Agent,",
                "  author = {Ada Alpha},",
                "  title = {Agentic Discovery Systems},",
                "  year = {2024},",
                "  journal = {ICLR},",
                "  doi = {10.1000/alpha},",
                "}",
                "",
                "@article{Beta2025Scientist,",
                "  author = {Ben Beta},",
                "  title = {AI Scientist Workflows},",
                "  year = {2025},",
                "  journal = {NeurIPS},",
                "  eprint = {2501.00001},",
                "}",
                "",
                "@article{Gamma2026Engineer,",
                "  author = {Gia Gamma},",
                "  title = {AI Engineer Agents},",
                "  year = {2026},",
                "  journal = {ICML},",
                "  doi = {10.1000/gamma},",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_library_list_returns_bounded_summaries(tmp_path):
    init_topic(tmp_path)
    _write_library(tmp_path)

    proc = subprocess.run(
        [str(ROOT / "bin" / "paper_engine"), "library", "list", "--root", str(tmp_path), "--limit", "2", "--json"],
        text=True,
        capture_output=True,
        check=True,
    )
    records = json.loads(proc.stdout)

    assert len(records) == 2
    assert records[0] == {
        "bibkey": "Alpha2024Agent",
        "title": "Agentic Discovery Systems",
        "year": "2024",
        "venue": "ICLR",
        "doi": "10.1000/alpha",
        "arxiv_id": None,
        "openalex_id": None,
    }
    assert "@article" not in proc.stdout
    assert "author" not in records[0]


def test_library_find_matches_summary_fields(tmp_path):
    init_topic(tmp_path)
    _write_library(tmp_path)

    proc = subprocess.run(
        [str(ROOT / "bin" / "paper_engine"), "library", "find", "--root", str(tmp_path), "--query", "2501.00001", "--json"],
        text=True,
        capture_output=True,
        check=True,
    )
    records = json.loads(proc.stdout)

    assert [record["bibkey"] for record in records] == ["Beta2025Scientist"]
    assert records[0]["arxiv_id"] == "2501.00001"


def test_library_update_metadata_renames_bibkey_and_marks_unverified(tmp_path):
    init_topic(tmp_path)
    _write_library(tmp_path)
    old_dir = tmp_path / "papers" / "Alpha2024Agent"
    old_dir.mkdir(parents=True)
    (old_dir / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    (old_dir / "metadata.yml").write_text("bibkey: Alpha2024Agent\ntitle: Old\n", encoding="utf-8")
    append_candidates(
        tmp_path,
        [
            {
                "title": "Agentic Discovery Systems",
                "authors": ["Ada Alpha"],
                "year": 2024,
                "venue": "ICLR",
                "abstract": "",
                "source": "fixture",
                "doi": "10.1000/alpha",
                "status": "in_library",
                "bibkey": "Alpha2024Agent",
            }
        ],
    )
    metadata = tmp_path / "alpha_fixed.json"
    metadata.write_text(
        json.dumps(
            {
                "title": "Corrected Agentic Discovery Systems",
                "authors": ["Ada Alpha", "Ben Beta"],
                "year": 2025,
                "venue": "Journal of Agentic Research",
                "doi": "10.1000/alpha-fixed",
                "arxiv_id": "2501.12345",
                "url": "https://example.org/alpha-fixed",
                "metadata_source_note": "agent checked Crossref and arXiv search results before writing this file",
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            str(ROOT / "bin" / "paper_engine"),
            "library",
            "update-metadata",
            "--root",
            str(tmp_path),
            "Alpha2024Agent",
            "--metadata",
            str(metadata),
            "--new-bibkey",
            "Alpha2025Corrected",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["old_bibkey"] == "Alpha2024Agent"
    assert payload["bibkey"] == "Alpha2025Corrected"
    assert payload["metadata_status"] == "unverified"
    assert payload["updated_candidates"] == ["CAND-001"]
    assert not old_dir.exists()
    new_dir = tmp_path / "papers" / "Alpha2025Corrected"
    assert (new_dir / "paper.pdf").exists()
    metadata_text = (new_dir / "metadata.yml").read_text(encoding="utf-8")
    assert "Alpha2025Corrected" in metadata_text
    assert "Corrected Agentic Discovery Systems" in metadata_text
    bib = (tmp_path / "library.bib").read_text(encoding="utf-8")
    assert "@article{Alpha2025Corrected," in bib
    assert "@article{Alpha2024Agent," not in bib
    assert "Corrected Agentic Discovery Systems" in bib
    assert "paperEngineMetadataStatus = {unverified}" in bib
    assert "paperEngineMetadataNote = {agent checked Crossref and arXiv search results before writing this file}" in bib
    assert "file = {papers/Alpha2025Corrected/paper.pdf}" in bib
    assert load_candidates(tmp_path)[0]["bibkey"] == "Alpha2025Corrected"
    assert check_bib(tmp_path)["ok"] is True


def test_library_update_metadata_rejects_existing_new_bibkey_without_changes(tmp_path):
    init_topic(tmp_path)
    _write_library(tmp_path)
    old_dir = tmp_path / "papers" / "Alpha2024Agent"
    old_dir.mkdir(parents=True)
    (old_dir / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    before_bib = (tmp_path / "library.bib").read_text(encoding="utf-8")
    metadata = tmp_path / "alpha_fixed.json"
    metadata.write_text(
        json.dumps({"title": "Corrected", "authors": ["Ada Alpha"], "year": 2025, "doi": "10.1000/alpha-fixed"}),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            str(ROOT / "bin" / "paper_engine"),
            "library",
            "update-metadata",
            "--root",
            str(tmp_path),
            "Alpha2024Agent",
            "--metadata",
            str(metadata),
            "--new-bibkey",
            "Beta2025Scientist",
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "new bibkey already exists" in proc.stderr
    assert (tmp_path / "library.bib").read_text(encoding="utf-8") == before_bib
    assert old_dir.exists()


def test_library_update_metadata_rejects_ungrounded_metadata_without_identifier(tmp_path):
    init_topic(tmp_path)
    _write_library(tmp_path)
    metadata = tmp_path / "bad.json"
    metadata.write_text(json.dumps({"title": "Invented Metadata", "authors": ["No One"], "year": 2026}), encoding="utf-8")
    before_bib = (tmp_path / "library.bib").read_text(encoding="utf-8")

    proc = subprocess.run(
        [
            str(ROOT / "bin" / "paper_engine"),
            "library",
            "update-metadata",
            "--root",
            str(tmp_path),
            "Alpha2024Agent",
            "--metadata",
            str(metadata),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 1
    assert "verified work-level source" in proc.stderr
    assert (tmp_path / "library.bib").read_text(encoding="utf-8") == before_bib


def test_library_update_metadata_accepts_openalex_without_doi_or_arxiv(tmp_path):
    init_topic(tmp_path)
    _write_library(tmp_path)
    metadata = tmp_path / "alpha_openalex.json"
    metadata.write_text(
        json.dumps(
            {
                "title": "Agentic Discovery Systems Without DOI",
                "authors": ["Ada Alpha"],
                "year": 2024,
                "venue": "Workshop on Agentic Systems",
                "openalex_id": "https://openalex.org/W123456789",
                "issn": "1234-5678",
                "url": "https://openalex.org/W123456789",
                "metadata_source_note": "agent checked OpenAlex work record and publisher page before writing this file",
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            str(ROOT / "bin" / "paper_engine"),
            "library",
            "update-metadata",
            "--root",
            str(tmp_path),
            "Alpha2024Agent",
            "--metadata",
            str(metadata),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["bibkey"] == "Alpha2024Agent"
    assert payload["metadata_status"] == "unverified"
    bib = (tmp_path / "library.bib").read_text(encoding="utf-8")
    assert "doi =" not in bib.split("@article{Alpha2024Agent,", 1)[1].split("\n}", 1)[0]
    assert "eprint =" not in bib.split("@article{Alpha2024Agent,", 1)[1].split("\n}", 1)[0]
    assert "openalexId = {https://openalex.org/W123456789}" in bib
    assert "issn = {1234-5678}" in bib
    assert "paperEngineMetadataStatus = {unverified}" in bib
    assert "paperEngineMetadataNote = {agent checked OpenAlex work record and publisher page before writing this file}" in bib
    assert check_bib(tmp_path)["ok"] is True

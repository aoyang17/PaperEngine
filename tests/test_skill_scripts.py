from __future__ import annotations

import json
import os
import stat
import subprocess
import tarfile
from io import BytesIO
from pathlib import Path

from conftest import ROOT


EXTRACT_SCRIPT = ROOT / "templates" / "skills" / "reference_expansion" / "scripts" / "extract_arxiv_bib_titles.py"
COLLECT_SCRIPT = ROOT / "templates" / "skills" / "literature_collect" / "scripts" / "collect_titles.py"
FORWARD_SCRIPT = ROOT / "templates" / "skills" / "forward_citation_expansion" / "scripts" / "collect_citing_titles.py"


def _make_tar(path: Path, files: dict[str, str]) -> None:
    with tarfile.open(path, "w") as archive:
        for name, content in files.items():
            payload = content.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, BytesIO(payload))


def test_extract_arxiv_bib_titles_from_source_archive(tmp_path: Path):
    archive = tmp_path / "source.tar"
    _make_tar(
        archive,
        {
            "refs/main.bib": """
@article{foo2025,
  title = {Universal Guidance for Diffusion Models},
  author = {Doe, Jane and Roe, Richard},
  year = {2025}
}
@inproceedings{bar2024,
  title = "Flow Matching at Test Time",
  author = "Smith, Alice",
  year = "2024"
}
""",
        },
    )
    out = tmp_path / "refs.tsv"
    env = dict(os.environ)
    env["TMPDIR"] = str(tmp_path)

    proc = subprocess.run(
        ["python3", str(EXTRACT_SCRIPT), "--source-archive", str(archive), "--out", str(out)],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["count"] == 2
    text = out.read_text(encoding="utf-8")
    assert "Universal Guidance for Diffusion Models" in text
    assert "Flow Matching at Test Time" in text
    assert not list(tmp_path.glob("paper_engine_refs_*"))


def test_extract_arxiv_bib_titles_rejects_path_traversal(tmp_path: Path):
    archive = tmp_path / "bad.tar"
    _make_tar(archive, {"../evil.bib": "@article{x,title={Bad},year={2026}}"})
    out = tmp_path / "refs.tsv"

    proc = subprocess.run(
        ["python3", str(EXTRACT_SCRIPT), "--source-archive", str(archive), "--out", str(out)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "unsafe archive member path" in proc.stderr
    assert not out.exists()


def test_extract_arxiv_bib_titles_requires_bib_titles(tmp_path: Path):
    archive = tmp_path / "empty.tar"
    _make_tar(archive, {"paper.tex": "No bibliography here."})
    out = tmp_path / "refs.tsv"

    proc = subprocess.run(
        ["python3", str(EXTRACT_SCRIPT), "--source-archive", str(archive), "--out", str(out)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode != 0
    assert "no .bib files with titles found" in proc.stderr
    assert not out.exists()


def test_collect_titles_calls_existing_cli_and_dedup(tmp_path: Path):
    calls = tmp_path / "calls.jsonl"
    fake = tmp_path / "paper_engine"
    fake.write_text(
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
Path({str(calls)!r}).open("a", encoding="utf-8").write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:3] == ["tool", "dedup"]:
    print(json.dumps({{"ok": True}}))
else:
    print(json.dumps({{"ok": True, "added": 1}}))
""",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    titles = tmp_path / "titles.txt"
    titles.write_text(
        """
1. Universal Guidance for Diffusion Models
- Flow Matching at Test Time
Universal Guidance for Diffusion Models
""",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            "python3",
            str(COLLECT_SCRIPT),
            "--root",
            str(tmp_path / "topic"),
            "--titles-file",
            str(titles),
            "--paper-engine",
            str(fake),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["titles_seen"] == 2
    assert payload["total_added"] == 2
    call_args = [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()]
    assert call_args[0][:3] == ["collect", "--root", str(tmp_path / "topic")]
    assert '"Universal Guidance for Diffusion Models"' in call_args[0]
    assert '"Flow Matching at Test Time"' in call_args[1]
    assert call_args[-1] == ["tool", "dedup", "--root", str(tmp_path / "topic"), "--fix", "--json"]


def test_forward_citation_helper_merges_sources_and_enriches_pdf_signals(tmp_path: Path):
    openalex = tmp_path / "openalex.json"
    semantic = tmp_path / "semantic.json"
    openalex.write_text(
        json.dumps(
            {
                "meta": {"count": 2},
                "results": [
                    {
                        "id": "https://openalex.org/W1",
                        "display_name": "Universal Guidance for Flow Models",
                        "publication_year": 2026,
                        "doi": "https://doi.org/10.48550/arXiv.2601.12345",
                        "cited_by_count": 4,
                        "authorships": [{"author": {"display_name": "Ada Render"}}],
                        "primary_location": {"landing_page_url": "https://arxiv.org/abs/2601.12345"},
                        "best_oa_location": {},
                        "locations": [],
                        "open_access": {"is_oa": True, "oa_url": "https://arxiv.org/abs/2601.12345"},
                    },
                    {
                        "id": "https://openalex.org/W2",
                        "display_name": "Closed Follow-up on Flow Control",
                        "publication_year": 2025,
                        "cited_by_count": 1,
                        "authorships": [],
                        "primary_location": {},
                        "best_oa_location": {},
                        "locations": [{"pdf_url": "https://example.org/followup.pdf"}],
                        "open_access": {"is_oa": True},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    semantic.write_text(
        json.dumps(
            {
                "data": [
                    {
                        "citingPaper": {
                            "paperId": "S1",
                            "title": "Universal Guidance for Flow Models",
                            "year": 2026,
                            "venue": "arXiv.org",
                            "authors": [{"name": "Ada Render"}, {"name": "Ben Flow"}],
                            "abstract": "A longer abstract about universal guidance.",
                            "externalIds": {"ArXiv": "2601.12345", "DOI": "10.48550/arXiv.2601.12345"},
                            "citationCount": 2,
                            "openAccessPdf": {"url": ""},
                            "url": "https://www.semanticscholar.org/paper/S1",
                        }
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out_json = tmp_path / "raw.json"
    out_tsv = tmp_path / "titles.tsv"
    admitted = tmp_path / "admitted.json"
    titles = tmp_path / "titles.txt"

    proc = subprocess.run(
        [
            "python3",
            str(FORWARD_SCRIPT),
            "--seed-title",
            "Functional Flow Matching",
            "--openalex-fixture",
            str(openalex),
            "--semantic-fixture",
            str(semantic),
            "--out-json",
            str(out_json),
            "--out-tsv",
            str(out_tsv),
            "--admitted-json",
            str(admitted),
            "--titles-out",
            str(titles),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    summary = json.loads(proc.stdout)
    assert summary["merged_count"] == 2
    assert summary["acquirable_count"] == 2
    records = json.loads(admitted.read_text(encoding="utf-8"))
    by_title = {record["title"]: record for record in records}
    assert by_title["Universal Guidance for Flow Models"]["pdf_url"] == "https://arxiv.org/pdf/2601.12345.pdf"
    assert by_title["Universal Guidance for Flow Models"]["arxiv_id"] == "2601.12345"
    assert set(by_title["Universal Guidance for Flow Models"]["forward_sources"]) == {"openalex", "semantic"}
    assert by_title["Closed Follow-up on Flow Control"]["pdf_url"] == "https://example.org/followup.pdf"
    assert "Universal Guidance for Flow Models" in out_tsv.read_text(encoding="utf-8")
    assert "Closed Follow-up on Flow Control" in titles.read_text(encoding="utf-8")


def test_forward_citation_helper_can_filter_to_acquirable_and_rejects_scholar_only(tmp_path: Path):
    openalex = tmp_path / "openalex.json"
    openalex.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "https://openalex.org/W3",
                        "display_name": "Metadata Only Citing Paper",
                        "publication_year": 2026,
                        "authorships": [],
                        "primary_location": {},
                        "best_oa_location": {},
                        "locations": [],
                        "open_access": {"is_oa": False},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    common = [
        "python3",
        str(FORWARD_SCRIPT),
        "--seed-title",
        "Seed",
        "--openalex-fixture",
        str(openalex),
        "--semantic-fixture",
        str(tmp_path / "missing-semantic.json"),
        "--out-json",
        str(tmp_path / "raw.json"),
        "--out-tsv",
        str(tmp_path / "titles.tsv"),
        "--admitted-json",
        str(tmp_path / "admitted.json"),
        "--titles-out",
        str(tmp_path / "titles.txt"),
        "--only-acquirable",
        "--json",
    ]
    (tmp_path / "missing-semantic.json").write_text('{"data":[]}', encoding="utf-8")
    proc = subprocess.run(common, text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["admitted_count"] == 0
    assert json.loads((tmp_path / "admitted.json").read_text(encoding="utf-8")) == []

    scholar_proc = subprocess.run(
        [
            "python3",
            str(FORWARD_SCRIPT),
            "--scholar-url",
            "https://scholar.google.com/scholar?cites=123",
            "--out-json",
            str(tmp_path / "raw2.json"),
            "--out-tsv",
            str(tmp_path / "titles2.tsv"),
            "--admitted-json",
            str(tmp_path / "admitted2.json"),
            "--titles-out",
            str(tmp_path / "titles2.txt"),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert scholar_proc.returncode == 2
    assert "not scraped" in scholar_proc.stdout


def test_forward_citation_helper_continues_when_one_source_fixture_is_bad(tmp_path: Path):
    openalex = tmp_path / "openalex.json"
    bad_semantic = tmp_path / "bad-semantic.json"
    openalex.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "https://openalex.org/W4",
                        "display_name": "OpenAlex Survives Semantic Failure",
                        "publication_year": 2026,
                        "doi": "https://doi.org/10.48550/arXiv.2602.00001",
                        "authorships": [],
                        "primary_location": {},
                        "best_oa_location": {},
                        "locations": [],
                        "open_access": {"is_oa": True},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    bad_semantic.write_text("not json", encoding="utf-8")
    proc = subprocess.run(
        [
            "python3",
            str(FORWARD_SCRIPT),
            "--seed-title",
            "Seed",
            "--openalex-fixture",
            str(openalex),
            "--semantic-fixture",
            str(bad_semantic),
            "--out-json",
            str(tmp_path / "raw.json"),
            "--out-tsv",
            str(tmp_path / "titles.tsv"),
            "--admitted-json",
            str(tmp_path / "admitted.json"),
            "--titles-out",
            str(tmp_path / "titles.txt"),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["merged_count"] == 1
    assert payload["warnings"]

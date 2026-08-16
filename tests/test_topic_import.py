from __future__ import annotations

import json

import pytest

from conftest import fixture_path
from battery_lit.acquire import acquire_pdf
from battery_lit.bib import promote_candidate
from battery_lit.candidates import append_candidates, load_candidates, save_candidates
from battery_lit.read import audit_deep_read_quality
from battery_lit.search import collect
from battery_lit.topic import init_topic
from battery_lit.topic_import import import_paper_from_topic


def _bundle(root, bibkey):
    paper = root / "papers" / bibkey
    deep = json.loads(fixture_path("deep_read_report.json").read_text())
    source_map = json.loads(fixture_path("source_map.json").read_text())
    index = json.loads(fixture_path("paper_index.json").read_text())
    plan = json.loads(fixture_path("note_plan.json").read_text())
    deep.update({"bibkey": bibkey, "pdf_path": f"papers/{bibkey}/paper.pdf", "parsed_markdown_path": f"papers/{bibkey}/parsed.md", "source_map_path": f"papers/{bibkey}/source_map.json"})
    source_map["paper"].update({"bibkey": bibkey, "pdf_path": f"papers/{bibkey}/paper.pdf", "parsed_markdown_path": f"papers/{bibkey}/parsed.md"})
    paper.joinpath("paper_index.json").write_text(json.dumps(index))
    paper.joinpath("source_map.json").write_text(json.dumps(source_map))
    paper.joinpath("note_plan.json").write_text(json.dumps(plan))
    paper.joinpath("deep_read.json").write_text(json.dumps(deep))
    paper.joinpath("parsed.md").write_text("# parsed\n")
    assert audit_deep_read_quality(root, bibkey)["ok"]


def _source(tmp_path):
    root = tmp_path / "source"
    init_topic(root, "Source", "fixtures")
    collect(root, fixture=fixture_path("search_results.json"))
    acquire_pdf(root, "CAND-001", fixture_path("example.pdf"))
    bibkey = promote_candidate(root, "CAND-001")["bibkey"]
    _bundle(root, bibkey)
    return root, bibkey


def _target(tmp_path):
    root = tmp_path / "target"
    init_topic(root, "Target", "fixtures")
    return root


def test_import_success_and_excludes_rendered_outputs(tmp_path):
    source, key = _source(tmp_path)
    target = _target(tmp_path)
    source_paper = source / "papers" / key
    source_paper.joinpath("note.md").write_text("do not import")
    source_paper.joinpath("reading_result.html").write_text("do not import")
    deep_read_path = source_paper / "deep_read.json"
    deep_read = json.loads(deep_read_path.read_text())
    deep_read["source_map_path"] = ".tmp/read_pool/old-run/draft/source_map.json"
    deep_read_path.write_text(json.dumps(deep_read))

    result = import_paper_from_topic(target, source, key)

    assert result["status"] == "imported"
    paper = target / "papers" / key
    assert paper.joinpath("deep_read.json").exists()
    assert paper.joinpath("note.md").exists()  # rebuilt, not copied
    assert not paper.joinpath("reading_result.html").exists()
    imported_report = json.loads(paper.joinpath("deep_read.json").read_text())
    assert imported_report["source_map_path"] == f"papers/{key}/source_map.json"
    assert load_candidates(target)[0]["status"] == "in_library"
    assert load_candidates(target)[0]["import_provenance"]["source_bibkey"] == key


def test_existing_identity_skips_before_missing_assets_and_mutation(tmp_path):
    source, key = _source(tmp_path)
    target = _target(tmp_path)
    first = import_paper_from_topic(target, source, key)
    (source / "papers" / key / "deep_read.json").unlink()
    before = (target / "library.bib").read_bytes()
    result = import_paper_from_topic(target, source, key)
    assert first["ok"] and result["status"] == "already_exists"
    assert (target / "library.bib").read_bytes() == before


def test_collision_rewrites_structured_paths(tmp_path):
    source, key = _source(tmp_path)
    target = _target(tmp_path)
    (source / "papers" / key / "parsed.md").write_text(f"asset: papers/{key}/page_images/page-001.png\n")
    # An unrelated occupied key forces normal make_bibkey suffixing.
    (target / "library.bib").write_text(
        f"@article{{{key},\n  author = {{Other}},\n  title = {{Other paper}},\n  year = {{2020}},\n  doi = {{10.1/other}},\n}}\n"
    )
    result = import_paper_from_topic(target, source, key)
    new_key = result["bibkey"]
    assert new_key != key
    data = json.loads((target / "papers" / new_key / "deep_read.json").read_text())
    assert data["bibkey"] == new_key
    assert f"papers/{new_key}/" in data["pdf_path"]
    assert f"papers/{new_key}/page_images/page-001.png" in (target / "papers" / new_key / "parsed.md").read_text()


def test_source_candidate_path_fields_are_not_imported(tmp_path):
    source, key = _source(tmp_path)
    target = _target(tmp_path)
    records = load_candidates(source)
    records[0]["file"] = f"papers/{key}/paper.pdf"
    records[0]["source_topic_scratch"] = "/tmp/source-only"
    save_candidates(source, records)

    import_paper_from_topic(target, source, key)

    imported = load_candidates(target)[0]
    assert "file" not in imported
    assert "source_topic_scratch" not in imported


def test_unique_target_candidate_is_reused_with_score(tmp_path):
    source, key = _source(tmp_path)
    target = _target(tmp_path)
    candidate = load_candidates(source)[0].copy()
    candidate.update({"candidate_id": "CAND-001", "record_id": "REC-abcdef123456", "status": "irrelevant", "decision": "irrelevant", "preference_recorded_decision": "irrelevant", "score": 0.71, "score_status": "scored", "score_reasons": ["target judgement"]})
    save_candidates(target, [candidate])
    import_paper_from_topic(target, source, key)
    records = load_candidates(target)
    assert len(records) == 1
    assert records[0]["score"] == 0.71 and records[0]["score_status"] == "scored"
    assert records[0]["bibkey"] == key
    assert records[0]["decision"] == "relevant"
    assert "preference_recorded_decision" not in records[0]


def test_ambiguous_target_candidates_fails_without_mutation(tmp_path):
    source, key = _source(tmp_path)
    target = _target(tmp_path)
    candidate = load_candidates(source)[0]
    first, second = candidate.copy(), candidate.copy()
    second.update({"candidate_id": "CAND-002", "record_id": "REC-fedcba654321"})
    save_candidates(target, [first, second])
    with pytest.raises(ValueError, match="ambiguous target"):
        import_paper_from_topic(target, source, key)
    assert not (target / "papers" / key).exists()


def test_missing_assets_and_identity_errors(tmp_path):
    source, key = _source(tmp_path)
    target = _target(tmp_path)
    (source / "papers" / key / "paper_index.json").unlink()
    with pytest.raises(ValueError, match="required source asset"):
        import_paper_from_topic(target, source, key)
    with pytest.raises(ValueError, match="distinct"):
        import_paper_from_topic(target, target, key)


def test_source_metadata_must_match_bibtex(tmp_path):
    source, key = _source(tmp_path)
    target = _target(tmp_path)
    metadata_path = source / "papers" / key / "metadata.yml"
    text = metadata_path.read_text(encoding="utf-8")
    metadata_path.write_text(text.replace("10.1234/example", "10.1234/different"), encoding="utf-8")

    with pytest.raises(ValueError, match="source BibTeX"):
        import_paper_from_topic(target, source, key)
    assert not (target / "papers" / key).exists()


def test_source_assets_must_not_use_symlinks(tmp_path):
    source, key = _source(tmp_path)
    target = _target(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    (source / "papers" / key / "visual_index.md").symlink_to(outside)

    with pytest.raises(ValueError, match="must not be a symlink"):
        import_paper_from_topic(target, source, key)
    assert not (target / "papers" / key).exists()


def test_rebuild_failure_rolls_back(monkeypatch, tmp_path):
    source, key = _source(tmp_path)
    target = _target(tmp_path)
    original_bib = (target / "library.bib").read_bytes()
    original_candidates = (target / "candidates.jsonl").read_bytes()
    monkeypatch.setattr("battery_lit.topic_import.rebuild_note", lambda *_: {"ok": False})
    with pytest.raises(ValueError, match="target import validation"):
        import_paper_from_topic(target, source, key)
    assert (target / "library.bib").read_bytes() == original_bib
    assert (target / "candidates.jsonl").read_bytes() == original_candidates
    assert not (target / "papers" / key).exists()
    assert not list((target / ".tmp" / "topic_import").glob("*"))

from __future__ import annotations

from battery_lit.candidates import append_candidates, update_candidate
from battery_lit.status import topic_status
from battery_lit.topic import init_topic


def test_total_papers_counts_only_library_entries(tmp_path):
    init_topic(tmp_path, "Status Topic", "count library papers only")
    append_candidates(
        tmp_path,
        [
            {"title": "Queued Candidate", "authors": ["Ada"], "year": 2026, "source": "fixture", "status": "new"},
            {"title": "Relevant Candidate", "authors": ["Grace"], "year": 2025, "source": "fixture", "status": "relevant"},
        ],
    )

    status = topic_status(tmp_path)

    assert status["total_papers"] == 0
    assert status["candidate_queue"] == 1
    assert status["candidates"] == 2

    (tmp_path / "library.bib").write_text(
        """
@article{Smith2024Paper,
  author = {Smith, Ada},
  title = {Rendered Paper},
  year = {2024},
  journal = {Example Venue},
}
""",
        encoding="utf-8",
    )
    update_candidate(tmp_path, "CAND-002", status="in_library", bibkey="Smith2024Paper")

    status = topic_status(tmp_path)

    assert status["total_papers"] == 1
    assert status["papers"] == 1
    assert status["candidates"] == 2
    assert status["candidate_queue"] == 1

from __future__ import annotations

import pytest

from battery_lit.codex_prompts import oa_fallback_prompt, parse_fallback_result


def test_oa_fallback_prompt_forbids_bad_sources():
    prompt = oa_fallback_prompt({"title": "Paper"})
    assert "Sci-Hub" in prompt
    assert "random file mirrors" in prompt
    assert "Return only JSON" in prompt


def test_fallback_result_parser_accepts_and_rejects():
    assert parse_fallback_result({"status": "needs_manual", "confidence": "low"})["status"] == "needs_manual"
    with pytest.raises(ValueError):
        parse_fallback_result({"status": "found", "confidence": "certain"})

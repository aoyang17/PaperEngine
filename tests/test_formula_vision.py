from __future__ import annotations

import json
from pathlib import Path

from conftest import fixture_path
from battery_lit.formula_vision import SubprocessFormulaVisionRunner, transcribe_formulas


class FakeFormulaRunner:
    def __init__(self, response: str | None = None, fail: Exception | None = None) -> None:
        self.response = response or '{"equations":[]}'
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def run(self, prompt: str, cwd: Path, images: list[Path]) -> str:
        self.calls.append({"prompt": prompt, "cwd": cwd, "images": images})
        if self.fail:
            raise self.fail
        return self.response


def _write_math_topic(tmp_path, bibkey="Example2026A"):
    paper_dir = tmp_path / "papers" / bibkey
    image_dir = paper_dir / "math_pages"
    image_dir.mkdir(parents=True)
    (image_dir / "page-001.png").write_bytes(b"fake image")
    (paper_dir / "math_index.json").write_text(
        json.dumps(
            {
                "schema_version": "v3-math-index-2026-06",
                "parse_quality": {"quality": "poor", "reasons": ["fixture"], "metrics": {}},
                "selected_pages": [1],
                "math_page_images": [f"papers/{bibkey}/math_pages/page-001.png"],
                "text_candidates": [],
                "vision_fallback": {
                    "needed": True,
                    "status": "pending",
                    "reasons": ["fixture"],
                    "image_paths": [f"papers/{bibkey}/math_pages/page-001.png"],
                    "instruction": "Use Codex image input; do not invent notation.",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return paper_dir


def test_formula_vision_runner_command_attaches_images(tmp_path):
    image = tmp_path / "page-001.png"
    runner = SubprocessFormulaVisionRunner(codex_bin="/usr/bin/codex", model="gpt-5.5", effort="medium")

    command = runner.command(tmp_path, [image])

    assert command[:4] == ["/usr/bin/codex", "exec", "--json", "--sandbox"]
    assert "--image" in command
    assert str(image) in command
    assert "read-only" in command
    assert "-C" in command
    assert command[-1] == "-"


def test_transcribe_formulas_writes_formula_vision_and_merges_source_map(tmp_path):
    paper_dir = _write_math_topic(tmp_path)
    source_map = json.loads(fixture_path("source_map.json").read_text(encoding="utf-8"))
    (paper_dir / "source_map.json").write_text(json.dumps(source_map, indent=2), encoding="utf-8")
    runner = FakeFormulaRunner(
        json.dumps(
            {
                "equations": [
                    {
                        "page": 1,
                        "label": "Optimal control objective",
                        "latex": "\\\\min_u J(u)",
                        "plain_text": "minimize J(u)",
                        "meaning": "The controller minimizes an objective.",
                        "variables": ["u: control"],
                        "confidence": "high",
                        "region_note": "top half of the page",
                    }
                ]
            }
        )
    )

    result = transcribe_formulas(tmp_path, "Example2026A", runner=runner)

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["equations"] == 1
    assert result["source_map_merged"] is True
    formula_vision = json.loads((paper_dir / "formula_vision.json").read_text(encoding="utf-8"))
    assert formula_vision["equations"][0]["latex"] == "\\\\min_u J(u)"
    merged = json.loads((paper_dir / "source_map.json").read_text(encoding="utf-8"))
    block = next(item for item in merged["blocks"] if item["id"] == "M001")
    assert block["source_kind"] == "equation"
    assert block["backend"] == "codex_cli_image_input"
    math_index = json.loads((paper_dir / "math_index.json").read_text(encoding="utf-8"))
    assert math_index["vision_fallback"]["status"] == "completed"


def test_transcribe_formulas_records_blocked_without_source_map_pollution(tmp_path):
    paper_dir = _write_math_topic(tmp_path)
    source_map = json.loads(fixture_path("source_map.json").read_text(encoding="utf-8"))
    (paper_dir / "source_map.json").write_text(json.dumps(source_map, indent=2), encoding="utf-8")
    runner = FakeFormulaRunner(fail=RuntimeError("namespace sandbox failed"))

    result = transcribe_formulas(tmp_path, "Example2026A", runner=runner)

    assert result["ok"] is True
    assert result["status"] == "blocked"
    formula_vision = json.loads((paper_dir / "formula_vision.json").read_text(encoding="utf-8"))
    assert formula_vision["status"] == "blocked"
    assert "namespace sandbox failed" in formula_vision["errors"][0]
    merged = json.loads((paper_dir / "source_map.json").read_text(encoding="utf-8"))
    assert not any(str(item.get("id", "")).startswith("M") for item in merged["blocks"])
    math_index = json.loads((paper_dir / "math_index.json").read_text(encoding="utf-8"))
    assert math_index["vision_fallback"]["status"] == "blocked"

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from battery_lit.acquire import acquire_pdf, check_pdfs
from battery_lit.bib import promote_candidate
from battery_lit.candidates import load_candidates, update_candidate
from battery_lit.citation_guard import check_bib
from battery_lit.html import build_html
from battery_lit.metadata import enrich_candidate
from battery_lit.read import parse_pdf
from battery_lit.search import collect
from battery_lit.topic import init_topic


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None)
    parser.add_argument("--topic", default="test-time guidance for generative flow model")
    parser.add_argument("--max-papers", type=int, default=2)
    parser.add_argument("--fixture")
    parser.add_argument("--fixture-pdf", default=str(ROOT / "tests" / "fixtures" / "example.pdf"))
    args = parser.parse_args()

    root = Path(args.root or ROOT / ".tmp" / "real_2paper_probe").resolve()
    root.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {"topic": args.topic, "root": str(root), "blockers": []}

    try:
        init_topic(root, title=args.topic, direction=args.topic)
        first = collect(root, query=args.topic, target_new=max(args.max_papers * 4, 8), fixture=args.fixture)
        second = collect(root, query=args.topic, target_new=max(args.max_papers * 4, 8), fixture=args.fixture)
        summary["collect"] = [first, second]

        promoted: list[str] = []
        for candidate in load_candidates(root):
            if len(promoted) >= args.max_papers:
                break
            cid = candidate["candidate_id"]
            update_candidate(root, cid, status="relevant", decision="probe")
            manual_pdf = args.fixture_pdf if args.fixture else None
            enrich_candidate(root, cid, live=not bool(args.fixture))
            result = acquire_pdf(root, cid, manual_pdf)
            if not result["ok"]:
                summary["blockers"].append({"candidate_id": cid, "stage": "acquire", "error": result.get("error")})
                continue
            try:
                promoted_result = promote_candidate(root, cid)
            except Exception as exc:
                summary["blockers"].append({"candidate_id": cid, "stage": "promote", "error": str(exc)})
                continue
            bibkey = promoted_result["bibkey"]
            parse_result = parse_pdf(root, bibkey)
            if not parse_result["ok"]:
                summary["blockers"].append({"candidate_id": cid, "stage": "parse", "error": parse_result.get("error")})
            promoted.append(bibkey)

        summary["promoted"] = promoted
        if promoted:
            summary["deep_read"] = {
                "status": "manual_skill_required",
                "skill": "skills/paper_deep_read/SKILL.md",
                "papers": [
                    {
                        "bibkey": bibkey,
                        "input": f"papers/{bibkey}/parsed.md",
                        "output": f"papers/{bibkey}/deep_read.json",
                    }
                    for bibkey in promoted
                ],
            }
        summary["bib"] = check_bib(root)
        summary["pdf"] = check_pdfs(root)
        summary["html"] = build_html(root)
        ok = len(promoted) >= 1 and summary["bib"]["ok"] and summary["pdf"]["ok"]
        summary["ok"] = ok
    except Exception as exc:
        summary["ok"] = False
        summary["blockers"].append({"stage": "probe", "error": str(exc)})

    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "real_probe_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

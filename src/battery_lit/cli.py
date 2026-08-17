from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


def emit(data: Any, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        print(data)


def _root_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=".", help="Topic repository root")


def _validate_serverlet_topic(root: str) -> None:
    root_path = Path(root).expanduser()
    required = ["topic.yml", "policy.yml", "preferences.yml"]
    missing = [name for name in required if not (root_path / name).exists()]
    if missing:
        raise FileNotFoundError(
            f"missing topic files under {root_path}: {', '.join(missing)}. "
            "Run `battery_lit init` before `battery_lit start`."
        )


def _auto_build_html(root: str) -> None:
    if str(os.environ.get("BATTERY_LIT_AUTO_HTML", "")).strip().lower() in {"0", "false", "no"}:
        return
    try:
        from .html import build_html

        build_html(root)
    except Exception as exc:
        print(f"warning: failed to auto-refresh HTML: {exc}", file=sys.stderr)


def _configure_start_codex_sandbox(use_codex_sandbox: bool) -> None:
    if use_codex_sandbox:
        os.environ.pop("BATTERY_LIT_CODEX_BYPASS_SANDBOX", None)
        print(
            "Codex workspace sandbox enabled; this may fail in Docker containers without user namespaces.",
            file=sys.stderr,
        )
        return
    os.environ["BATTERY_LIT_CODEX_BYPASS_SANDBOX"] = "1"
    print(
        "Codex sandbox disabled for this serverlet; battery_lit policy and CLI remain the safety boundary.",
        file=sys.stderr,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="battery_lit")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser(
        "init",
        description=(
            "Initialize a clean-room topic repository. Do not inspect existing topic folders, "
            "sibling directories, .agents, or .codex to infer initialization conventions."
        ),
        epilog="If --title or --direction is missing, ask the user; do not infer from filesystem.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_init.add_argument("--root", default=None, help="Topic repository root. If omitted, use --base-dir plus a slugified --title.")
    p_init.add_argument("--base-dir", help="Parent directory for a topic root generated from --title")
    p_init.add_argument("--title")
    p_init.add_argument("--direction")
    p_init.add_argument("--seed-paper", action="append", default=[])

    p_status = sub.add_parser("status")
    _root_arg(p_status)
    p_status.add_argument("--json", action="store_true")

    p_start = sub.add_parser("start", description="Start the serverlet-first browser workbench for a topic.")
    p_start.add_argument("--root", default=None, help="Existing topic repository root. Defaults to current directory when --base-dir is omitted.")
    p_start.add_argument("--base-dir", help="Start a bootstrap workbench that creates a new topic under this parent directory")
    p_start.add_argument("--host", default="127.0.0.1")
    p_start.add_argument("--port", type=int, default=10005)
    p_start.add_argument(
        "--codex-sandbox",
        action="store_true",
        help=(
            "Run Codex turns with the Codex workspace sandbox. By default, start disables the Codex sandbox "
            "because Docker user-namespace restrictions can block battery_lit itself."
        ),
    )

    p_policy = sub.add_parser("policy")
    psub = p_policy.add_subparsers(dest="policy_command", required=True)
    p_pcheck = psub.add_parser("check")
    _root_arg(p_pcheck)
    p_pcheck.add_argument("--json", action="store_true")

    p_preferences = sub.add_parser("preferences")
    prefsub = p_preferences.add_subparsers(dest="preferences_command", required=True)
    p_prefcheck = prefsub.add_parser("check")
    _root_arg(p_prefcheck)
    p_prefcheck.add_argument("--json", action="store_true")

    p_collect = sub.add_parser("collect")
    _root_arg(p_collect)
    p_collect.add_argument("--query")
    p_collect.add_argument("--fixture")
    p_collect.add_argument("--target-new", type=int, default=20)
    p_collect.add_argument("--score-threshold", type=float)

    p_candidates = sub.add_parser("candidates")
    csub = p_candidates.add_subparsers(dest="candidate_command", required=True)
    p_clist = csub.add_parser("list")
    _root_arg(p_clist)
    p_clist.add_argument("--json", action="store_true")
    p_clist.add_argument("--status")
    p_clist.add_argument("--limit", type=int)
    p_clist.add_argument("--sort", choices=["candidate_id", "score", "year", "title"], default="candidate_id")
    p_clist.add_argument("--min-score", type=float)
    p_cshow = csub.add_parser("show")
    _root_arg(p_cshow)
    p_cshow.add_argument("candidate_id")
    p_cshow.add_argument("--json", action="store_true")
    p_cmark = csub.add_parser("mark")
    _root_arg(p_cmark)
    p_cmark.add_argument("candidate_id")
    p_cmark.add_argument("decision", choices=["relevant", "irrelevant", "none"])
    p_cdismiss = csub.add_parser("dismiss")
    _root_arg(p_cdismiss)
    p_cdismiss.add_argument("candidate_id")
    p_crepair = csub.add_parser("repair")
    _root_arg(p_crepair)
    p_crepair.add_argument("--fix", action="store_true")
    p_crepair.add_argument("--json", action="store_true")
    p_cprune = csub.add_parser("prune-record")
    _root_arg(p_cprune)
    p_cprune.add_argument("--record-id", required=True)
    p_cprune.add_argument("--json", action="store_true")
    p_cremove_by_bibkey = csub.add_parser("remove-by-bibkey")
    _root_arg(p_cremove_by_bibkey)
    p_cremove_by_bibkey.add_argument("bibkey")
    p_cremove_by_bibkey.add_argument("--json", action="store_true")
    p_cscorebatch = csub.add_parser("scoring-batch")
    _root_arg(p_cscorebatch)
    p_cscorebatch.add_argument("--status", default="new")
    p_cscorebatch.add_argument("--limit", type=int, default=20)
    p_cscorebatch.add_argument("--min-score", type=float)
    p_cscorebatch.add_argument("--json", action="store_true")
    p_capplyscores = csub.add_parser("apply-scores")
    _root_arg(p_capplyscores)
    p_capplyscores.add_argument("--scores", required=True)

    p_acquire = sub.add_parser("acquire")
    _root_arg(p_acquire)
    p_acquire.add_argument("candidate_id")
    p_acquire.add_argument("--manual-pdf")

    p_promote = sub.add_parser("promote")
    _root_arg(p_promote)
    p_promote.add_argument("candidate_id")

    p_library = sub.add_parser("library")
    lsub = p_library.add_subparsers(dest="library_command", required=True)
    p_llist = lsub.add_parser("list")
    _root_arg(p_llist)
    p_llist.add_argument("--limit", type=int)
    p_llist.add_argument("--json", action="store_true")
    p_lfind = lsub.add_parser("find")
    _root_arg(p_lfind)
    p_lfind.add_argument("--query", required=True)
    p_lfind.add_argument("--limit", type=int)
    p_lfind.add_argument("--json", action="store_true")
    p_lupdate = lsub.add_parser("update-metadata")
    _root_arg(p_lupdate)
    p_lupdate.add_argument("bibkey")
    p_lupdate.add_argument("--metadata", required=True)
    p_lupdate.add_argument("--new-bibkey")
    p_lupdate.add_argument("--json", action="store_true")
    p_limport_topic = lsub.add_parser(
        "import-from-topic",
        description="Import one library paper from an explicitly named source topic.",
    )
    _root_arg(p_limport_topic)
    p_limport_topic.add_argument("--source-root", required=True, help="Source topic repository root")
    p_limport_topic.add_argument("--source-bibkey", required=True, help="Bibkey in the source topic library")
    p_limport_topic.add_argument("--json", action="store_true")

    p_bib = sub.add_parser("bib")
    bsub = p_bib.add_subparsers(dest="bib_command", required=True)
    p_bcheck = bsub.add_parser("check")
    _root_arg(p_bcheck)

    p_pdf = sub.add_parser("pdf")
    pdfsub = p_pdf.add_subparsers(dest="pdf_command", required=True)
    p_pdfcheck = pdfsub.add_parser("check")
    _root_arg(p_pdfcheck)

    p_read = sub.add_parser("read")
    _root_arg(p_read)
    p_read.add_argument("bibkey")
    p_read.add_argument("--parse-only", action="store_true")
    p_read.add_argument("--vision-formulas", action="store_true")
    p_read.add_argument("--validate-report", action="store_true")
    p_read.add_argument("--quality-audit", action="store_true")
    p_read.add_argument("--rebuild-note", action="store_true")

    p_read_batch = sub.add_parser("read-batch")
    _root_arg(p_read_batch)
    p_read_batch.add_argument("--bibkey", action="append", default=[])
    p_read_batch.add_argument("--all-library", action="store_true")
    p_read_batch.add_argument("--force-reread", action="store_true")
    p_read_batch.add_argument("--run-id")
    p_read_batch.add_argument("--finalize", action="store_true")
    p_read_batch.add_argument("--harvest", action="store_true")
    p_read_batch.add_argument("--draft-workers", action="store_true")
    p_read_batch.add_argument("--max-parallel", type=int)
    p_read_batch.add_argument("--repair-bibkey", action="append", default=[])
    p_read_batch.add_argument("--repair-error", action="append", default=[])
    p_read_batch.add_argument("--model")
    p_read_batch.add_argument("--effort")
    p_read_batch.add_argument("--json", action="store_true")

    p_read_many = sub.add_parser("read-many")
    _root_arg(p_read_many)
    p_read_many.add_argument("--bibkey", action="append", default=[])
    p_read_many.add_argument("--all-library", action="store_true")
    p_read_many.add_argument("--force-reread", action="store_true")
    p_read_many.add_argument("--refresh-section", choices=["dataset"])
    p_read_many.add_argument("--run-id")
    p_read_many.add_argument("--max-parallel", type=int)
    p_read_many.add_argument("--max-cycles", type=int, default=3)
    p_read_many.add_argument("--accept-last-on-max-cycles", action="store_true")
    p_read_many.add_argument("--model")
    p_read_many.add_argument("--effort")
    p_read_many.add_argument("--json", action="store_true")

    p_html = sub.add_parser("html")
    hsub = p_html.add_subparsers(dest="html_command", required=True)
    p_hbuild = hsub.add_parser("build")
    _root_arg(p_hbuild)
    p_hexport = hsub.add_parser("export")
    _root_arg(p_hexport)
    p_hexport.add_argument("bibkey")
    p_hexport.add_argument("--output")

    p_web = sub.add_parser("web")
    wsub = p_web.add_subparsers(dest="web_command", required=True)
    p_wserve = wsub.add_parser("serve")
    _root_arg(p_wserve)
    p_wserve.add_argument("--host", default="127.0.0.1")
    p_wserve.add_argument("--port", type=int, default=10005)

    p_tool = sub.add_parser("tool")
    tsub = p_tool.add_subparsers(dest="tool_command", required=True)
    p_tsearch = tsub.add_parser("search")
    p_tsearch.add_argument("--query", required=True)
    p_tsearch.add_argument("--fixture")
    p_tsearch.add_argument("--json", action="store_true")
    p_tresolve = tsub.add_parser("resolve-paper")
    _root_arg(p_tresolve)
    p_tresolve.add_argument("query")
    p_tresolve.add_argument("--json", action="store_true")
    p_tenrich = tsub.add_parser("enrich-metadata")
    _root_arg(p_tenrich)
    p_tenrich.add_argument("--candidate", required=True)
    p_tenrich.add_argument("--live", action="store_true")
    p_tenrich.add_argument("--json", action="store_true")
    p_tdedup = tsub.add_parser("dedup")
    _root_arg(p_tdedup)
    p_tdedup.add_argument("--fix", action="store_true")
    p_tdedup.add_argument("--json", action="store_true")
    p_tscore = tsub.add_parser("score")
    _root_arg(p_tscore)
    p_tscore.add_argument("--json", action="store_true")
    p_tguard = tsub.add_parser("citation-guard")
    _root_arg(p_tguard)
    p_tguard.add_argument("--candidate", required=True)
    p_tguard.add_argument("--json", action="store_true")
    p_tfallback = tsub.add_parser("codex-fallback")
    _root_arg(p_tfallback)
    p_tfallback.add_argument("--candidate", required=True)
    p_tfallback.add_argument("--json", action="store_true")
    p_taudit = tsub.add_parser("audit-readings")
    _root_arg(p_taudit)
    p_taudit.add_argument("--json", action="store_true")

    return parser


def run(args: argparse.Namespace) -> int:
    if args.command == "init":
        from .topic import init_topic, root_from_title

        if not args.title:
            raise ValueError("battery_lit init requires --title; ask the user; do not infer from filesystem")
        if not args.direction:
            raise ValueError("battery_lit init requires --direction; ask the user; do not infer from filesystem")

        root = args.root
        if root is None and args.base_dir:
            root = root_from_title(args.base_dir, args.title)
        root = root or "."
        emit(init_topic(root, args.title, args.direction, args.seed_paper))
        _auto_build_html(str(root))
        return 0

    if args.command == "status":
        from .status import topic_status

        status = topic_status(args.root)
        emit(status, as_json=args.json)
        return 0 if status["ok"] else 1

    if args.command == "start":
        from .web_app import serve_web

        if args.base_dir and args.root is not None:
            raise ValueError("--root and --base-dir are mutually exclusive for battery_lit start")
        if args.base_dir:
            _configure_start_codex_sandbox(args.codex_sandbox)
            serve_web(None, args.host, args.port, base_dir=args.base_dir)
            return 0
        root = args.root or "."
        _validate_serverlet_topic(root)
        _configure_start_codex_sandbox(args.codex_sandbox)
        serve_web(root, args.host, args.port, base_dir=None)
        return 0

    if args.command == "policy" and args.policy_command == "check":
        from .policy import check_policy

        result = check_policy(args.root)
        emit(result, as_json=args.json)
        return 0 if result["ok"] else 1

    if args.command == "preferences" and args.preferences_command == "check":
        from .preferences import check_preferences

        result = check_preferences(args.root)
        emit(result, as_json=args.json)
        return 0 if result["ok"] else 1

    if args.command == "collect":
        from .search import collect

        emit(collect(args.root, query=args.query, fixture=args.fixture, target_new=args.target_new, score_threshold=args.score_threshold))
        _auto_build_html(args.root)
        return 0

    if args.command == "candidates":
        from .candidates import get_candidate, load_candidates, mark_candidate, remove_candidate_by_record_id, remove_candidates_by_bibkey, repair_candidate_records
        from .preferences import mark_candidate_with_feedback

        if args.candidate_command == "list":
            records = load_candidates(args.root)
            if args.status:
                records = [record for record in records if record.get("status") == args.status]
            if args.min_score is not None:
                records = [record for record in records if float(record.get("score") or 0.0) >= args.min_score]
            if args.sort == "score":
                records = sorted(records, key=lambda record: float(record.get("score") or 0.0), reverse=True)
            elif args.sort == "year":
                records = sorted(records, key=lambda record: record.get("year") or 0, reverse=True)
            elif args.sort == "title":
                records = sorted(records, key=lambda record: str(record.get("title") or "").lower())
            else:
                records = sorted(records, key=lambda record: str(record.get("candidate_id") or ""))
            if args.limit is not None:
                records = records[: max(args.limit, 0)]
            emit(records, as_json=args.json)
            return 0
        if args.candidate_command == "show":
            emit(get_candidate(args.root, args.candidate_id), as_json=args.json)
            return 0
        if args.candidate_command == "mark":
            emit(mark_candidate_with_feedback(args.root, args.candidate_id, args.decision))
            _auto_build_html(args.root)
            return 0
        if args.candidate_command == "dismiss":
            emit(mark_candidate(args.root, args.candidate_id, "dismissed"))
            _auto_build_html(args.root)
            return 0
        if args.candidate_command == "repair":
            result = repair_candidate_records(args.root, fix=args.fix)
            emit(result, as_json=args.json)
            if args.fix:
                _auto_build_html(args.root)
            return 0 if result["ok"] else 1
        if args.candidate_command == "prune-record":
            result = remove_candidate_by_record_id(args.root, args.record_id)
            emit(result, as_json=args.json)
            if result["ok"]:
                _auto_build_html(args.root)
            return 0 if result["ok"] else 1
        if args.candidate_command == "remove-by-bibkey":
            result = remove_candidates_by_bibkey(args.root, args.bibkey)
            emit(result, as_json=args.json)
            if result["ok"]:
                _auto_build_html(args.root)
            return 0 if result["ok"] else 1
        if args.candidate_command == "scoring-batch":
            from .scoring import export_scoring_batch

            emit(export_scoring_batch(args.root, args.status, args.limit, args.min_score), as_json=args.json)
            return 0
        if args.candidate_command == "apply-scores":
            from .scoring import apply_candidate_scores

            emit(apply_candidate_scores(args.root, args.scores))
            _auto_build_html(args.root)
            return 0

    if args.command == "acquire":
        from .acquire import acquire_pdf

        result = acquire_pdf(args.root, args.candidate_id, args.manual_pdf)
        emit(result)
        _auto_build_html(args.root)
        return 0 if result["ok"] else 1

    if args.command == "promote":
        from .bib import promote_candidate

        emit(promote_candidate(args.root, args.candidate_id))
        _auto_build_html(args.root)
        return 0

    if args.command == "library":
        if args.library_command == "list":
            from .bib import list_library

            emit(list_library(args.root, args.limit), as_json=args.json)
            return 0
        if args.library_command == "find":
            from .bib import find_library

            emit(find_library(args.root, args.query, args.limit), as_json=args.json)
            return 0
        if args.library_command == "update-metadata":
            from .bib import update_library_metadata

            result = update_library_metadata(args.root, args.bibkey, args.metadata, new_bibkey=args.new_bibkey)
            emit(result, as_json=args.json)
            _auto_build_html(args.root)
            return 0
        if args.library_command == "import-from-topic":
            from .topic_import import import_paper_from_topic

            result = import_paper_from_topic(args.root, args.source_root, args.source_bibkey)
            emit(result, as_json=args.json)
            if result.get("status") == "imported":
                _auto_build_html(args.root)
            return 0 if result.get("status") in {"imported", "already_exists"} else 1

    if args.command == "bib" and args.bib_command == "check":
        from .citation_guard import check_bib

        result = check_bib(args.root)
        emit(result)
        return 0 if result["ok"] else 1

    if args.command == "pdf" and args.pdf_command == "check":
        from .acquire import check_pdfs

        result = check_pdfs(args.root)
        emit(result)
        return 0 if result["ok"] else 1

    if args.command == "read":
        from .read import audit_deep_read_quality, parse_pdf, rebuild_note, validate_deep_read_report

        result = {"ok": False, "error": "choose --parse-only, --vision-formulas, --validate-report, --quality-audit, or --rebuild-note"}
        if args.parse_only:
            result = parse_pdf(args.root, args.bibkey)
        elif args.vision_formulas:
            from .formula_vision import transcribe_formulas

            result = transcribe_formulas(args.root, args.bibkey)
        elif args.validate_report:
            result = validate_deep_read_report(args.root, args.bibkey)
        elif args.quality_audit:
            result = audit_deep_read_quality(args.root, args.bibkey)
        elif args.rebuild_note:
            result = rebuild_note(args.root, args.bibkey)
        emit(result)
        if args.rebuild_note and result["ok"]:
            _auto_build_html(args.root)
        return 0 if result["ok"] else 1

    if args.command == "read-batch":
        from .read_batch import finalize_read_batch, prepare_read_batch, run_read_batch_draft_workers

        if args.finalize:
            if not args.run_id:
                raise ValueError("read-batch --finalize requires --run-id")
            result = finalize_read_batch(args.root, args.run_id)
            emit(result, as_json=args.json)
            if result["ok"]:
                _auto_build_html(args.root)
            return 0 if result["ok"] else 1
        if args.harvest or args.draft_workers:
            if not args.run_id:
                raise ValueError("read-batch --draft-workers requires --run-id")
            manifest_path = Path(args.root).expanduser() / ".tmp" / "read_batch" / args.run_id / "manifest.json"
            prepared = None
            if not manifest_path.exists():
                if not args.bibkey and not args.all_library:
                    result = {"ok": False, "error": f"missing read-batch manifest: {manifest_path}"}
                    emit(result, as_json=args.json)
                    return 1
                prepared = prepare_read_batch(
                    args.root,
                    bibkeys=args.bibkey,
                    all_library=args.all_library,
                    force_reread=args.force_reread,
                    run_id=args.run_id,
                )
                if not prepared.get("ok"):
                    emit(prepared, as_json=args.json)
                    return 1
            result = run_read_batch_draft_workers(
                args.root,
                args.run_id,
                max_parallel=args.max_parallel,
                model=args.model,
                effort=args.effort,
                repair_bibkeys=args.repair_bibkey,
                repair_errors=args.repair_error,
                progress=lambda message: print(message, file=sys.stderr, flush=True),
            )
            if prepared is not None:
                result = {**result, "prepared": prepared}
            emit(result, as_json=args.json)
            return 0 if result["ok"] else 1
        result = prepare_read_batch(
            args.root,
            bibkeys=args.bibkey,
            all_library=args.all_library,
            force_reread=args.force_reread,
            run_id=args.run_id,
        )
        emit(result, as_json=args.json)
        return 0 if result["ok"] else 1

    if args.command == "read-many":
        from .read_pool import run_read_pool

        result = run_read_pool(
            args.root,
            bibkeys=args.bibkey,
            all_library=args.all_library,
            force_reread=args.force_reread,
            refresh_section=args.refresh_section,
            run_id=args.run_id,
            max_parallel=args.max_parallel,
            max_cycles=args.max_cycles,
            accept_last_on_max_cycles=args.accept_last_on_max_cycles,
            model=args.model,
            effort=args.effort,
            progress=lambda message: print(message, file=sys.stderr, flush=True),
        )
        emit(result, as_json=args.json)
        return 0 if result["ok"] else 1

    if args.command == "html" and args.html_command == "build":
        from .html import build_html

        emit(build_html(args.root))
        return 0

    if args.command == "html" and args.html_command == "export":
        from .html import export_standalone_html

        emit(export_standalone_html(args.root, args.bibkey, args.output))
        return 0

    if args.command == "web" and args.web_command == "serve":
        from .web_app import serve_web

        serve_web(args.root, args.host, args.port)
        return 0

    if args.command == "tool":
        if args.tool_command == "search":
            from .search import load_search_fixture, run_backend_search

            records = load_search_fixture(args.fixture) if args.fixture else run_backend_search(args.query)
            emit({"ok": True, "results": records}, as_json=True)
            return 0
        if args.tool_command == "resolve-paper":
            from .search import resolve_paper

            emit(resolve_paper(args.root, args.query), as_json=True)
            return 0
        if args.tool_command == "enrich-metadata":
            from .metadata import enrich_candidate

            emit(enrich_candidate(args.root, args.candidate, live=args.live), as_json=True)
            _auto_build_html(args.root)
            return 0
        if args.tool_command == "dedup":
            from .dedup import deduplicate_candidates

            result = deduplicate_candidates(args.root, fix=args.fix)
            emit(result, as_json=True)
            if args.fix:
                _auto_build_html(args.root)
            return 0 if result["ok"] else 1
        if args.tool_command == "score":
            from .candidates import load_candidates

            records = [{**record, "computed_score": float(record.get("score") or 0.0)} for record in load_candidates(args.root)]
            emit({"ok": True, "candidates": records}, as_json=True)
            return 0
        if args.tool_command == "citation-guard":
            from .citation_guard import citation_guard_candidate

            result = citation_guard_candidate(args.root, args.candidate)
            emit(result, as_json=True)
            return 0 if result["ok"] else 1
        if args.tool_command == "codex-fallback":
            from .candidates import get_candidate
            from .codex_prompts import oa_fallback_prompt

            candidate = get_candidate(args.root, args.candidate)
            emit({"ok": True, "prompt": oa_fallback_prompt(candidate)}, as_json=True)
            return 0
        if args.tool_command == "audit-readings":
            from .read import audit_reading_library

            result = audit_reading_library(args.root)
            emit(result, as_json=args.json)
            return 0 if result["ok"] else 1

    raise RuntimeError(f"unhandled command: {args}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

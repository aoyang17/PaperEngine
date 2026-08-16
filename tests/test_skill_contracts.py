from __future__ import annotations

from conftest import ROOT


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _repo_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_repository_entry_routes_without_sibling_context():
    text = _repo_text("AGENTS.md")
    assert "Silicon-Carbon Anode Literature Agent Guide" in text
    assert "Use `bin/battery_lit`" in text
    assert "Do not call `battery_lit init` with missing title or direction" in text
    assert "silicon-carbon negative-electrode materials" in text
    assert "Do not inspect `.agents`, `.codex`, hidden directories" in text
    assert "locate application root" not in text
    assert "locate the application root" not in text


def test_repository_readme_uses_product_language():
    text = _repo_text("README.md")
    assert "structured literature review of silicon-carbon negative-electrode materials" in text
    assert "research_profile/scope.md" in text
    assert "@/battery_research_literature/README.md" in text
    assert "使用 battery_lit 工具" in text
    assert "名字定为 \"<topic title>\"" in text
    assert "检索方向是 <one paragraph research direction>" in text
    assert "bin/battery_lit init --base-dir /tmp" in text
    assert "locate application root" not in text


def test_agents_context_budget_and_safety_contract():
    text = _text("templates/topic_repo/AGENTS.md")
    assert "policy.yml" in text
    assert "Codex is not the only safety boundary" in text
    assert "battery_lit policy check --json" in text
    assert "Do not read these large files or trees in full by default" in text
    assert "library.bib" in text
    assert "candidates.jsonl" in text
    assert "battery_lit library list --json --limit 20" in text
    assert "battery_lit library find --json --query TEXT" in text
    assert "battery_lit library update-metadata <bibkey> --metadata <file> --json" in text
    assert "dry-run list and explicit user confirmation" in text
    assert "Do not bypass the CLI" in text
    assert "Parent directories and sibling topic folders are out of scope" in text
    assert "use sibling topics as templates" in text
    assert "skills/reference_expansion/SKILL.md" in text
    assert "skills/forward_citation_expansion/SKILL.md" in text
    assert "battery_lit candidates remove-by-bibkey <bibkey> --json" in text
    assert "only removes one unique matching record from `candidates.jsonl`" in text
    assert "if multiple queue items match the same bibkey it fails without deleting anything" in text
    assert "must not be treated as permission to delete `library.bib`, `papers/<bibkey>/`, PDFs, notes" in text
    assert "Metadata supplied by an agent must be grounded in real search/source results" in text
    assert "never invented from model memory" in text
    assert "BibTeX field `batteryMetadataStatus` with value `unverified`" in text


def test_project_agents_routes_init_and_enter():
    text = _text("AGENTS.md")
    assert "templates/skills/topic_init/SKILL.md" in text
    assert "templates/skills/topic_enter/SKILL.md" in text
    assert "Do not call `battery_lit init` with missing title or direction" in text
    assert "Do not run exploratory directory commands to confirm initialization conventions" in text
    assert "do not run `ls <base-dir>`" in text
    assert "Missing title or direction must be resolved by asking the user" in text
    assert "--base-dir" in text
    assert "safe slugified folder name" in text
    assert "--direction \"<direction>\"" in text
    assert "user_description_raw" in text
    assert "immediately enter the new topic" in text
    assert "Topic initialization is clean-room by default" in text
    assert "Do not list, search, read, summarize, copy, or use sibling folders" in text
    assert "templates/topic_repo/" in text
    assert "Do not inspect `.agents`, `.codex`, hidden directories" in text


def test_readme_documents_serverlet_first_entry():
    text = _text("README.md")
    assert "Serverlet-first entry" in text
    assert "battery_lit start --base-dir <parent-dir>" in text
    assert "battery_lit start --root <topic>" in text
    assert "browser workbench is the ordinary interface" in text
    assert "persistent Codex session" in text
    assert "External interactive Codex is an advanced/debug fallback" in text
    assert "@/battery_research_literature/README.md" in text
    assert "使用 battery_lit 工具" in text
    assert "动力电池硅碳负极" in text
    assert "规模制造和全电池验证" in text
    assert "Do not ask Codex to \"load the battery_lit agent\"" in text
    assert "multi-agent delegation" in text
    assert "templates/skills/topic_init/SKILL.md" in text
    assert "skills/topic_enter/SKILL.md" in text
    assert "--base-dir" in text
    assert "silicon-carbon-anodes-for-traction-batteries" in text
    assert "user_description_raw" in text
    assert "avoid reading full `library.bib`, `candidates.jsonl`, or `papers/*`" in text
    assert "base directory is not a context source" in text
    assert "should not inspect sibling topics or use them as templates" in text
    assert "Ordinary init does not require listing parent directories" in text
    assert "If required inputs are missing, ask the user instead of inferring from local files" in text


def test_user_manuals_document_browser_default():
    english = _text("docs/user_manual.md")
    chinese = _text("docs/user_manual_zh.md")
    assert "battery_lit start --base-dir <parent-dir>" in english
    assert "battery_lit start --root <topic>" in english
    assert "browser workbench" in english
    assert "persistent Codex operator" in english
    assert "External Codex" in english
    assert "battery_lit start --base-dir <parent-dir>" in chinese
    assert "battery_lit start --root <topic>" in chinese
    assert "浏览器" in chinese
    assert "持续存在的 Codex 操作员" in chinese
    assert "外部 Codex" in chinese
    assert "advanced/debug fallback" in english
    assert "高级维护或调试 fallback" in chinese


def test_user_manuals_document_paper_reread_skill():
    english = _text("docs/user_manual.md")
    chinese = _text("docs/user_manual_zh.md")
    readme = _text("README.md")
    assert "paper_reread" in english
    assert "do not reuse existing deep_read/note/html as evidence" in english
    assert "paper_reread" in chinese
    assert "不要复用已有 deep_read/note/html 作为证据" in chinese
    assert "skills/paper_reread/SKILL.md" in readme
    assert "overwrite the old knowledge card" in readme


def test_paper_deep_read_skill_rejects_unsupported_survey_matrix_rows():
    skill = _text("templates/skills/paper_deep_read/SKILL.md")
    contract = _text("templates/skills/paper_deep_read/references/output-contract.md")
    assert "A survey matrix row is allowed only when the paper evidence supports a concrete mechanism" in skill
    assert "do not add low-confidence filler rows" in skill
    assert "Each method-family row must be evidence-backed" in contract
    assert "put that in `coverage_gaps` or `extraction_notes.missing_sections` instead" in contract
    assert "Every quick-read item must name a concrete method" in skill
    assert "Availability reader-facing `evidence` fields must interpret" in skill
    assert "Every quick-read item must name a concrete method" in contract
    assert "Availability evidence must interpret" in contract


def test_paper_deep_read_skill_requires_structured_dataset_contract():
    skill = _text("templates/skills/paper_deep_read/SKILL.md")
    types = _text("templates/skills/paper_deep_read/references/paper-type-contracts.md")
    contract = _text("templates/skills/paper_deep_read/references/output-contract.md")
    assert "For active `dataset_benchmark`, use the `structured_v2` contract" in skill
    assert '`format: "structured_v2"`' in types
    assert "dataset-at-a-glance table, not an experiment-results dump" in types
    assert "construction_steps" in types
    assert "Do not emit the legacy `data_construction`/`statistics` list shape for new reads" in contract
    assert "Dataset key numbers describe the corpus itself" in contract


def test_live_testing_documents_five_paper_reading_quality_gate():
    text = _text("docs/live_testing.md")
    assert "Reading Quality Acceptance" in text
    assert "--min-papers 5" in text
    assert "--per-paper-timeout 1800" in text
    assert "at least five distinct papers" in text
    assert "BATTERY_LIT_ALLOW_UNSANDBOXED_PROBE=1" in text
    assert "--codex-bypass-sandbox" in text
    assert "Do not report a one-paper smoke test as reading-quality live acceptance" in text
    assert "successful_rereads" in text
    assert "battery_lit tool audit-readings --json" in text
    assert "note.md" in text
    assert "note_zh.md" in text
    assert "reading_result.html" in text


def test_topic_init_skill_refines_rough_description():
    text = _text("templates/skills/topic_init/SKILL.md")
    assert "Do not call `battery_lit init` with missing title or direction" in text
    assert "Do Not Explore Before Init" in text
    assert "First contact rule" in text
    assert "use `bin/battery_lit init` directly" in text
    assert "Do not search for local examples or similar topics first" in text
    assert "Do not run `ls <base-dir>`" in text
    assert "do not run `find .agents .codex`" in text
    assert "If title or direction is missing, ask the user directly" in text
    assert "Do not infer missing inputs from the filesystem" in text
    assert "Topic Folder Name" in text
    assert "slugifies the title" in text
    assert "Do not use the raw title as a folder name" in text
    assert "Clean-room Init Boundary" in text
    assert "Allowed context during ordinary init" in text
    assert "Forbidden context during ordinary init" in text
    assert "Do not list, search, read, summarize, copy, or use sibling folders" in text
    assert "sibling paths under the base directory, regardless of name" in text
    assert "`.agents`, `.codex`, hidden directories" in text
    assert "Do not initialize a topic by imitating another topic under any parent directory" in text
    assert "target topic root already exists and is non-empty" in text
    assert "Do not copy the user's rough description directly into final `direction`" in text
    assert "user_description_raw" in text
    assert "search.seed_queries" in text
    assert "search.exclude_terms" in text
    assert "Optional Search Preview" in text
    assert "Ask 2-4 short multiple-choice" in text
    assert "skills/topic_enter/SKILL.md" in text


def test_topic_enter_skill_bootstraps_without_large_reads():
    text = _text("templates/skills/topic_enter/SKILL.md")
    assert "battery_lit policy check --root <topic> --json" in text
    assert "battery_lit status --root <topic> --json" in text
    assert "Do not read full `library.bib`" in text
    assert "Report the topic title, policy health, status counts" in text


def test_topic_readme_points_to_topic_enter_not_large_files():
    text = _text("templates/topic_repo/README.md")
    assert "skills/topic_enter/SKILL.md" in text
    assert "policy.yml" in text
    assert "Do not read `library.bib`, `candidates.jsonl`, or `papers/*` in full" in text


def test_topic_policy_declares_parent_and_sibling_boundary():
    text = _text("templates/topic_repo/policy.yml")
    assert "parent directories and sibling topic folders as out of scope" in text
    assert "root_boundary: \"current topic root only\"" in text
    assert "parent_and_sibling_topics: \"out of scope unless explicitly requested" in text


def test_collect_skill_uses_cli_dedup_not_full_bibtex_context():
    text = _text("templates/skills/literature_collect/SKILL.md")
    assert "Do not read full `library.bib` or `candidates.jsonl`" in text
    assert "battery_lit status --json" in text
    assert "battery_lit tool dedup --fix --json" in text
    assert "skills/candidate_scoring/SKILL.md" in text
    assert "battery_lit library find --json --query TEXT" in text
    assert "Exact Title Intake" in text
    assert "Batch Title Intake" in text
    assert "skills/literature_collect/scripts/collect_titles.py" in text
    assert "skills/reference_expansion/SKILL.md" in text
    assert "Constrained Collection" in text
    assert "candidate list is the admission gate" in text
    assert "battery_lit tool search --root <topic> --query" in text
    assert "Rejected preview hits must not be written to `candidates.jsonl`" in text
    assert "Exact-title candidates must be scored before reporting them as ready for screening" in text
    assert "Batch-title candidates must also be scored before screening" in text
    assert "Preference-Aware Search" in text
    assert "query_hints" in text
    assert "exclude_hints" in text
    assert "Batch Sidecar Acceleration" in text
    assert "Good sidecar work: query variants" in text
    assert "Bad sidecar work: writing `candidates.jsonl`" in text
    assert "cleaned after the main worker consumes them" in text


def test_candidate_scoring_skill_bounds_sidecar_shards():
    text = _text("templates/skills/candidate_scoring/SKILL.md")
    assert "Batch Sidecar Acceleration" in text
    assert "sidecars may speed up the judgment step only" in text
    assert "The main Codex worker still owns validation" in text
    assert "Sidecars must not run `battery_lit candidates apply-scores`" in text
    assert "Reject malformed JSONL" in text
    assert "Remove temporary sidecar directories" in text


def test_topic_agents_declares_sidecar_state_boundary():
    text = _text("templates/topic_repo/AGENTS.md")
    assert "Sidecar / Subagent Boundary" in text
    assert "battery_lit read-many" in text
    assert "one reader session and one independent reviewer session per paper" in text
    assert ".tmp/read_pool/<run_id>/<bibkey>/draft/" in text
    assert "only the controller may copy accepted artifacts into `papers/<bibkey>/`" in text
    assert "Forbidden sidecar actions" in text
    assert "editing `candidates.jsonl`, `library.bib`, `preferences.yml`" in text
    assert "running `battery_lit collect`, `tool dedup --fix`, `candidates apply-scores`" in text
    assert "writing final `source_map.json`, `note_plan.json`, or `deep_read.json`" in text
    assert "Do not merge multi-paper reading artifacts by hand" in text


def test_live_testing_documents_subagent_adversarial_probe():
    text = _text("docs/live_testing.md")
    assert "Subagent Adversarial Probe" in text
    assert "scripts/run_subagent_adversarial_probe.py --json" in text
    assert "topic-level job locking blocks concurrent state writers" in text
    assert "malformed or out-of-range score shards" in text
    assert "temporary sidecar workspaces are removed by default" in text


def test_paper_reread_skill_scales_probe_size_to_change_scope():
    text = _text("templates/skills/paper_reread/SKILL.md")
    assert "Probe Sizing" in text
    assert "Use the smallest realistic probe that matches the change being tested" in text
    assert "Documentation, skill wording, or test-only edits" in text
    assert "Do not start a new live Codex reread probe" in text
    assert "Prompt or quality-gate edits: test a mixed three-paper run" in text
    assert "with `--max-parallel 3`" in text
    assert "Reader/reviewer orchestration, retry, finalization, or repeated-text audit edits: test at least five papers" in text
    assert "All-library or large-run edits" in text
    assert "The second and third live validation rounds may be merged" in text
    assert "After a scoped probe passes, stop and report the evidence" in text
    assert "Avoid adding phrase lists or one-off validators" in text


def test_preference_refresh_skill_is_llm_driven_and_bounded():
    text = _text("templates/skills/preference_refresh/SKILL.md")
    assert "LLM synthesis task, not a rule-based keyword extractor" in text
    assert "battery_lit preferences check --root <topic> --json" in text
    assert "at most 40 labeled candidates" in text
    assert "Do not read PDFs" in text
    assert "Do not update `topic.yml`" in text
    assert "Every `like`, `dislike`, `query_hints`, and `exclude_hints` item must be supported" in text
    assert "dismissed` candidates are not semantic preference evidence" in text


def test_reference_expansion_skill_uses_bundled_scripts_and_tmp_hygiene():
    text = _text("templates/skills/reference_expansion/SKILL.md")
    assert "reference_expansion" in text
    assert "battery_lit candidates show --root <topic> CAND-ID --json" in text
    assert "skills/reference_expansion/scripts/extract_arxiv_bib_titles.py" in text
    assert "skills/literature_collect/scripts/collect_titles.py" in text
    assert "battery_lit tool dedup --root <topic> --fix --json" in text
    assert "skills/candidate_scoring/SKILL.md" in text
    assert "Do not create fixed `/tmp/<task>` directories" in text
    assert "Do not read full `candidates.jsonl`, `library.bib`, or sibling topic folders" in text
    assert "Only admitted titles should be passed to `collect_titles.py`" in text
    assert "do not preserve rejected hits in `candidates.jsonl`" in text
    assert "follow `skills/candidate_scoring/SKILL.md` before reporting the expansion complete" in text
    assert "After direct title-list intake adds candidates" in text


def test_forward_citation_expansion_skill_uses_api_not_google_scholar_scraping():
    text = _text("templates/skills/forward_citation_expansion/SKILL.md")
    assert "forward_citation_expansion" in text
    assert "papers that cite a named seed paper" in text
    assert "Do not read full `library.bib`, full `candidates.jsonl`" in text
    assert "Google Scholar" in text
    assert "do not scrape or paginate Google Scholar" in text
    assert "OpenAlex" in text
    assert "Semantic Scholar" in text
    assert "Do not treat OpenAlex as a PDF source" in text
    assert "primary_location`, `best_oa_location`, and every `locations[*]`" in text
    assert "https://arxiv.org/pdf/<arxiv_id>.pdf" in text
    assert "reports/forward_citation_admitted_<seed>.json" in text
    assert "battery_lit collect --root <topic>" in text
    assert "--fixture reports/forward_citation_admitted_<seed>.json" in text
    assert "battery_lit tool dedup --root <topic> --fix --json" in text
    assert "skills/candidate_scoring/SKILL.md" in text
    assert "metadata_only" in text
    assert "acquirable" in text


def test_candidate_scoring_skill_defines_relevance_rubric():
    text = _text("templates/skills/candidate_scoring/SKILL.md")
    assert "Score each candidate for topic relevance in `[-1, 1]`" in text
    assert "`content` in `[-0.70, 0.70]`" in text
    assert "`preference` in `[-0.15, 0.15]`" in text
    assert "`credibility` in `[-0.15, 0.15]`" in text
    assert "Do not use DOI, PDF URL, publication year, search backend, or retrieval source" in text
    assert "battery_lit candidates scoring-batch" in text
    assert "battery_lit candidates apply-scores" in text
    assert "Preview Scoring Before Admission" in text
    assert "score raw `battery_lit tool search --json` preview results" in text
    assert "Preview results below threshold are search hits, not candidates" in text


def test_paper_deep_read_skill_requires_chinese_coverage_pass():
    skill = _text("templates/skills/paper_deep_read/SKILL.md")
    contract = _text("templates/skills/paper_deep_read/references/output-contract.md")
    assert "Run an explicit Chinese coverage pass before validation" in skill
    assert "structurally mirror the reader-facing English fields" in skill
    assert "Do not copy English sentences into Chinese fields as a fallback" in skill
    assert "Run an explicit interpretation-quality pass before validation" in skill
    assert "Do not paste long source paragraphs" in skill
    assert "躺平式" in skill
    assert "validator rejects missing, copied-English, mostly-English, parser-residue, template-like, or lazy generic reader text" in skill
    assert "Chinese coverage is part of the output contract" in contract
    assert "Interpretation quality is also part of the output contract" in contract
    assert "not paste source blocks into templates" in contract
    assert "copied English text is not acceptable as a fallback" in contract
    assert "Markdown and HTML should not rely on English fallback" in contract
    assert "adjacent-domain reader" in contract
    assert "concrete intervention or analysis route" in contract
    assert "tasks, baselines, or benchmarks" in contract


def test_paper_reread_skill_prevents_old_artifact_contamination():
    skill = _text("templates/skills/paper_reread/SKILL.md")
    agents = _text("templates/topic_repo/AGENTS.md")
    assert "reread" in agents
    assert "skills/paper_reread/SKILL.md" in agents
    assert "Existing reading artifacts are targets to replace, not evidence to reuse" in skill
    assert "do not use these files as reading evidence" in skill
    assert "papers/<bibkey>/deep_read.json" in skill
    assert "papers/<bibkey>/note.md" in skill
    assert "papers/<bibkey>/reading_result.html" in skill
    assert "battery_lit read <bibkey> --parse-only" in skill
    assert "battery_lit read <bibkey> --vision-formulas" in skill
    assert "skills/paper_deep_read/SKILL.md" in skill
    assert "battery_lit read <bibkey> --validate-report" in skill
    assert "battery_lit read <bibkey> --quality-audit" in skill
    assert "battery_lit read <bibkey> --rebuild-note" in skill
    assert "battery_lit read-many --bibkey <bibkey>" in skill
    assert "battery_lit read-many --all-library --force-reread --json" in skill
    assert "battery_lit read-many --bibkey <bibkey> --refresh-section dataset --json" in skill
    assert "do not run a full reread" in skill
    assert "Do not mention rereading, updating, old results" in skill
    assert "one reader session and one independent reviewer session" in skill
    assert "let `read-many` use 5 paper jobs" in skill
    assert "Use `--max-parallel N` above 5 only when the user explicitly asks" in skill
    assert "hard cap is 20 paper jobs" in skill
    assert "up to 2N Codex sessions" in skill
    assert "at most three reader-review cycles by default" in skill
    assert "project hard cap is 7" in skill
    assert "Do not use `--accept-last-on-max-cycles` unless the user explicitly asks" in skill
    assert "deterministic draft writer" in skill
    assert "parsed/index-only bulk generator" in skill
    assert "schema filler" in skill
    assert "If `read-many` reports a failed bibkey" in skill
    assert skill.rindex("battery_lit read <bibkey> --rebuild-note") < skill.rindex("battery_lit read <bibkey> --quality-audit")


def test_paper_reread_skill_limits_subagents_to_reader_reviewer_jobs():
    skill = _text("templates/skills/paper_reread/SKILL.md")
    assert "reader/reviewer sessions inside `battery_lit read-many` are the default path" in skill
    assert "The main Codex session must not write multi-paper draft contents" in skill
    assert "generate that paper's staged `source_map.json`, `note_plan.json`, `deep_read.json`" in skill
    assert "Do not write final `papers/<bibkey>/` artifacts" in skill
    assert "Do not let the main session or several subagents write final `deep_read.json` files directly" in skill
    assert "Do not split one paper into several writers" in skill
    assert "Do not let subagents use old notes or old `deep_read.json` as a source" in skill
    assert "write `reader.json` provenance" in skill
    assert "Write only `review.json`" in skill
    assert "feeds that paper-specific feedback back to the same reader session" in skill


def test_paper_deep_read_skill_uses_evidence_harvest_workflow():
    skill = _text("templates/skills/paper_deep_read/SKILL.md")
    contract = _text("templates/skills/paper_deep_read/references/output-contract.md")

    workflow = "evidence-harvest -> interpretation-draft -> schema-write -> self-review gate"
    assert workflow in skill
    assert workflow in contract
    assert skill.index("evidence-harvest") < skill.index("interpretation-draft")
    assert skill.index("interpretation-draft") < skill.index("schema-write")
    assert skill.index("schema-write") < skill.index("self-review gate")
    assert "Do not use the schemas as the first writing outline" in skill
    assert "harvest evidence before drafting interpretations" in contract
    assert "self-review gate must pass before validation" in contract


def test_paper_deep_read_requires_external_availability_evidence_blocks():
    skill = _text("templates/skills/paper_deep_read/SKILL.md")
    contract = _text("templates/skills/paper_deep_read/references/output-contract.md")
    source_map = _text("templates/skills/paper_deep_read/references/source-map.md")

    assert "External Availability Search Protocol" in skill
    assert "code, data, and model availability" in skill
    assert "do not rely only on the paper text" in skill
    assert "limited external search" in skill
    assert "E### external source block" in skill
    assert "E###" in contract
    assert "availability.code`, `availability.data`, and `availability.models`" in contract
    assert "at least one local source ref or one `E###` external source block" in contract
    assert "If external search is blocked or unavailable" in contract
    assert "`E001`, `E002`, ... for external availability evidence." in source_map
    assert "`source_kind: \"external\"`" in source_map
    assert "Record the external page title, URL, access date, and search query or lookup path in `notes`" in source_map


def test_paper_deep_read_keeps_internal_instructions_out_of_reader_output():
    skill = _text("templates/skills/paper_deep_read/SKILL.md")
    contract = _text("templates/skills/paper_deep_read/references/output-contract.md")

    assert "quality-audit wording" in skill
    assert "Never mention \"this reread\"" in skill
    assert "Reader-facing Markdown, HTML, and `deep_read.json` prose must not mention prompt instructions" in contract
    assert "the fact that the job is a reread" in contract
    assert "`note_plan.json` is internal planning evidence, not reader-facing content" in contract
    assert "validation and quality-audit errors are repair instructions, not content to summarize" in contract
    assert "selected evidence" in contract


def test_acquire_skill_keeps_bibtex_guarded():
    text = _text("templates/skills/paper_acquire_bib/SKILL.md")
    assert "Do not directly edit `library.bib`" in text
    assert "battery_lit tool enrich-metadata" in text
    assert "battery_lit tool citation-guard" in text
    assert "battery_lit acquire" in text
    assert "battery_lit promote" in text
    assert "battery_lit bib check" in text
    assert "Temporary PDF Hygiene" in text
    assert "Do not use fixed paths such as `/tmp/paper.pdf`" in text


def test_deep_read_skill_is_one_paper_and_chunked():
    text = _text("templates/skills/paper_deep_read/SKILL.md")
    assert "Read one paper at a time" in text
    assert "Do not scan every paper directory" in text
    assert "references/paper-profile.md" in text
    assert "references/paper-type-contracts.md" in text
    assert "references/reading-plan.md" in text
    assert "references/source-map.md" in text
    assert "references/argument-anatomy.md" in text
    assert "references/numeric-results.md" in text
    assert "references/visual-card.md" in text
    assert "references/output-contract.md" in text
    assert "evidence-harvest" in text
    assert "interpretation-draft" in text
    assert "schema-write" in text
    assert "self-review gate" in text
    assert "key equations" in text.lower()
    assert "theorem/principle chain" in text.lower()
    assert "method-family matrix" in text.lower()
    assert "papers/<bibkey>/math_index.json" in text
    assert "papers/<bibkey>/math_pages/page-*.png" in text
    assert "papers/<bibkey>/formula_vision.json" in text
    assert "vision_fallback.needed" in text
    assert "vision_fallback.status" in text
    assert "battery_lit read <bibkey> --vision-formulas" in text
    assert "only allowed Codex image-input exception" in text
    assert "central claims" in text.lower()
    assert "source_refs" in text
    assert "page_images/contact_sheet.jpg" in text
    assert "source_map.json" in text
    assert "note_plan.json" in text
    assert "deep_read.json" in text
    assert "`read --rebuild-note` refreshes static HTML automatically" in text
    assert "BATTERY_LIT_AUTO_HTML=0" in text
    profile = _text("templates/skills/paper_deep_read/references/paper-profile.md")
    source_map = _text("templates/skills/paper_deep_read/references/source-map.md")
    argument = _text("templates/skills/paper_deep_read/references/argument-anatomy.md")
    visual = _text("templates/skills/paper_deep_read/references/visual-card.md")
    output = _text("templates/skills/paper_deep_read/references/output-contract.md")
    type_contracts = _text("templates/skills/paper_deep_read/references/paper-type-contracts.md")
    reading_plan = _text("templates/skills/paper_deep_read/references/reading-plan.md")
    numeric_results = _text("templates/skills/paper_deep_read/references/numeric-results.md")
    assert "`method` plus `application`" in profile
    assert "source_map.json" in source_map
    assert "paper_index.json" in source_map
    assert "source IDs" in source_map
    assert "gap" in argument and "what_it_does_not_prove" in argument
    assert "full_page_approximate" in visual
    assert "reading_note" in visual
    assert "placement_section" in visual
    assert "caption, page number, and `image_path`" in visual
    assert "visual_cards" in output
    assert "math_index.json" in output
    assert "formula_vision.json" in output
    assert "note_plan.json" in output
    assert "translations.zh" in output
    assert "algorithm_steps" in output
    assert "algorithm_pseudocode" in output
    assert "engineering_derivation_sketch" in output
    assert "key_equations" in output
    assert "theorem_or_principle_chain" in output
    assert "method_family_matrix" in output
    assert "extraction_notes" in output
    assert "dataset_benchmark_understanding" in type_contracts
    assert "engineering_proof_sketch" in type_contracts
    assert "problem_formulation" in type_contracts
    assert "key_equations" in type_contracts
    assert "method_family_matrix" in type_contracts
    assert "timeline_milestones" in type_contracts
    assert "equation" in source_map and "method_family" in source_map
    assert "active_lenses" in reading_plan
    assert "what_it_does_not_prove" in numeric_results
    assert "parser, page-rendering, source-map" in numeric_results


def test_digest_skill_uses_summaries_before_notes():
    text = _text("templates/skills/literature_digest/SKILL.md")
    assert "Do not read full `library.bib`" in text
    assert "battery_lit library list --json --limit 50" in text
    assert "battery_lit library find --json --query TEXT" in text
    assert "Read `papers/<bibkey>/note.md` only for papers needed" in text


def test_public_guides_do_not_use_development_stage_names():
    public_paths = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "bin" / "battery_lit",
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "templates" / "topic_repo" / "README.md",
        ROOT / "templates" / "topic_repo" / "AGENTS.md",
        ROOT / "templates" / "topic_repo" / "policy.yml",
        ROOT / "templates" / "skills" / "topic_init" / "SKILL.md",
        ROOT / "templates" / "skills" / "literature_collect" / "SKILL.md",
        ROOT / "third_party" / "README.md",
        ROOT / "docs" / "feature_coverage.md",
        ROOT / "docs" / "user_manual.md",
        ROOT / "docs" / "user_manual_zh.md",
        ROOT / "docs" / "deployment.md",
        ROOT / "src" / "battery_lit" / "__init__.py",
    ]
    banned = ["V1", "V2", "V1_legacy", "legacy", "archived"]
    for path in public_paths:
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{token} should not appear in {path}"

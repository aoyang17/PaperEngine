# Feature Coverage

This document tracks user-facing capability coverage for PaperEngine.

| Category | Current behavior | Tests |
|---|---|---|
| init | `paper_engine init --root` or `--base-dir` creates a file-only topic repository, AGENTS, skills, schemas, and initial HTML | `test_topic_init.py` |
| topic config | `topic.yml` plus `preferences.yml` define the topic and screening preferences | `test_topic_init.py`, `test_preferences.py` |
| search | self-contained paper search backend plus fixtures | `test_search_dedup.py` |
| seed/resolve paper | seed papers in `topic.yml`, `tool resolve-paper` | `test_topic_init.py`, `test_search_dedup.py` |
| candidate queue | `candidates.jsonl` with status and decision fields | `test_candidates.py` |
| preference feedback | file preferences with batched term updates | `test_preferences.py` |
| PDF download | open-access/manual acquire into paper-centric directories | `test_acquire_bib.py` |
| BibTeX | verified metadata, unique keys, and relative PDF file checks | `test_acquire_bib.py`, `test_citation_guard.py` |
| paper-centric files | `papers/<bibkey>/metadata.yml`, `paper.pdf`, `parsed.md`, `visual_index.md`, `page_images/*`, `deep_read.json`, `note.md`, `reading_result.html` | `test_acquire_bib.py`, `test_read.py`, `test_html.py` |
| parse/deep-read/note | parse text, generate lightweight visual evidence, validate the full JSON schema, and rebuild note/report pages | `test_read.py` |
| checks | status, `bib check`, `pdf check`, and `tool citation-guard` | `test_citation_guard.py` |
| serverlet browser workbench | `paper_engine start --base-dir` launches the Create Topic UI, binds after Codex init, and `start --root` launches an existing topic with command console, quick actions, job status, candidates, library, and paper pages | `test_cli_start.py`, `test_web_bootstrap.py`, `test_web_actions.py`, `test_serverlet_workflow.py`, `test_web_rendering.py` |
| HTML view | static report pages remain available for export and paper knowledge browsing | `test_html.py`, `test_web_skeleton.py`, `test_web_rendering.py` |
| simulation reproduction | five-stage Research → Theory → Implementation → Experiment → Review controller, gateway-aware remote COMSOL Agent, immutable rework archives, solver-neutral metrics and fail-closed acceptance | `test_simulation_reproduction.py`, `test_laghmach2015_postprocess.py` |
| real probe | real 2-paper probe script with explicit blockers | `test_real_probe_contract.py` |

The current implementation intentionally keeps state file-based, avoids desktop bibliography manager coupling, and routes browser actions through Codex operation jobs instead of a second business backend.

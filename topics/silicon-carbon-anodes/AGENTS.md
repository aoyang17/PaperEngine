# Topic Operating Guide

This topic is operated through the browser workbench and bounded Codex operation jobs. Treat `battery_lit` as the deterministic tool layer and the topic-local `skills/` directory as the operating manual.

Safety is defined by `policy.yml`, project tools, the execution sandbox, and user approval. Codex should follow the policy, but Codex is not the only safety boundary.

## Context Budget

Read these small files at the start of a session:

- `AGENTS.md`
- `policy.yml`
- `topic.yml`
- `preferences.yml`

Do not read these large files or trees in full by default:

- `library.bib`
- `candidates.jsonl`
- `papers/*/parsed.md`
- `papers/*/page_images/*`
- `papers/*/math_pages/*`
- `papers/*/formula_vision.json`
- `papers/*/deep_read.json`
- `papers/*/paper.pdf`

Use CLI summaries first:

- `battery_lit policy check --json`
- `battery_lit status --json`
- `battery_lit library list --json --limit 20`
- `battery_lit library find --json --query TEXT`
- `battery_lit library update-metadata <bibkey> --metadata <file> --json`
- `battery_lit candidates list --json --status STATUS`
- `battery_lit candidates remove-by-bibkey <bibkey> --json`
- `battery_lit bib check`
- `battery_lit pdf check`
- `battery_lit tool dedup --fix --json`

Read a paper directory only after the user or workflow names a specific `bibkey`. Read a candidate only after the user or workflow names a specific `candidate_id`.

## Topic Boundary

The default working boundary is this topic root. Parent directories and sibling topic folders are out of scope.

Do not read, search, summarize, copy from, or use sibling topics as templates unless the user explicitly asks to migrate, copy, compare, or reference a specific external topic path.

## Short Commands

Map short user requests to the matching skill:

- collect, search, find papers, add candidates -> `skills/literature_collect/SKILL.md`
- follow references, mine citations, collect from a bibliography, batch title intake -> `skills/reference_expansion/SKILL.md`
- find newer papers citing a seed paper, follow cited-by links, forward citation expansion -> `skills/forward_citation_expansion/SKILL.md`
- score, rank, prioritize candidates -> `skills/candidate_scoring/SKILL.md`
- screen, rank, mark relevant or irrelevant -> `skills/preference_screen/SKILL.md`
- update or refresh preferences from labels -> `skills/preference_refresh/SKILL.md`
- download PDF, acquire, promote, add to library, import a paper from another topic -> `skills/paper_acquire_bib/SKILL.md`
- read paper, deep read, knowledge card, note -> `skills/paper_deep_read/SKILL.md`
- reread, re-interpret, refresh/repair reading result, overwrite stale knowledge card -> `skills/paper_reread/SKILL.md`
- summarize, digest, progress report -> `skills/literature_digest/SKILL.md`

Users should not need to say "read topic.yml", "deduplicate", or "check library.bib". These are default duties of the matching skill.

If the user asks to remove or clean up a candidate queue item by `bibkey`, use `battery_lit candidates remove-by-bibkey <bibkey> --json`. This command only removes one unique matching record from `candidates.jsonl`; if multiple queue items match the same bibkey it fails without deleting anything, and the next step is dedup or a specific candidate ID. It must not be treated as permission to delete `library.bib`, `papers/<bibkey>/`, PDFs, notes, `reading_result.html`, or any other paper asset.

If the user asks to correct a library paper's metadata or bibkey, prepare a small JSON/YAML metadata file and call `battery_lit library update-metadata <bibkey> --metadata <file> --json`; add `--new-bibkey <key>` only when the bibkey itself should change. Metadata supplied by an agent must be grounded in real search/source results, checked repeatedly against title, authors, year, DOI/arXiv, and venue, and never invented from model memory. The command writes the BibTeX field `batteryMetadataStatus` with value `unverified` because battery_lit did not independently verify the supplied metadata.

For a cross-topic paper import, the user must explicitly name the source topic path. Use `skills/paper_acquire_bib/SKILL.md`: resolve a title through controlled `battery_lit library find --root <source-topic> --query TEXT --json` only when it has exactly one match, then run `battery_lit library import-from-topic --root <target-topic> --source-root <source-topic> --source-bibkey <bibkey> --json`. Never shell-copy or directly edit `library.bib`, `candidates.jsonl`, PDFs, or paper directories. Report `imported`, `already_exists`, and skipped results clearly. A successful import creates an `in_library` candidate with decision `relevant`; it does not immediately refresh `preferences.yml`.

## Safety Boundary

Read `policy.yml` before any state-changing task.

Use `battery_lit` for state changes whenever it has a command for the task. Do not bypass the CLI to edit `library.bib`, candidate status, PDF placement, or generated HTML.

Allowed direct writes:

- `papers/<bibkey>/source_map.json`
- `papers/<bibkey>/note_plan.json`
- `papers/<bibkey>/deep_read.json`
- `reports/*.json` or `reports/*.md`
- small user-facing notes requested by the user

Generated parser/report files such as `parsed.md`, `visual_index.md`, `page_images/*`, `note.md`, and `reading_result.html` should be produced by `battery_lit` commands, not by hand.

Never invent citations, PDFs, BibTeX, metadata, or paper claims. If metadata, DOI/arXiv, open PDF evidence, or source support is missing, report a blocker.

Never run destructive operations such as deleting the topic, clearing `library.bib`, clearing `candidates.jsonl`, removing `papers/`, or bulk-overwriting paper directories without a dry-run list and explicit user confirmation. If no safe CLI exists for a requested mutation, report the blocker or propose the smallest CLI addition.

For single-paper deep reading, the current Codex operation worker should follow `skills/paper_deep_read/SKILL.md` and write the full paper-local reading bundle itself: `source_map.json`, `note_plan.json`, and `deep_read.json`. If the user explicitly asks to reread or overwrite stale reading output, first follow `skills/paper_reread/SKILL.md` so old artifacts are not reused as evidence. For multi-paper rereads, use the controlled `battery_lit read-many` runner; if that runner is unavailable, stop and report the blocker instead of processing papers sequentially in the main session.

## Sidecar / Subagent Boundary

Multi-paper reading/rereading should use `battery_lit read-many` by default. It runs one reader session and one independent reviewer session per paper. Readers may write only staged drafts under `.tmp/read_pool/<run_id>/<bibkey>/draft/` plus `reader.json`; reviewers may write only `review.json`; only the controller may copy accepted artifacts into `papers/<bibkey>/`.

Allowed sidecar outputs:

- query suggestions, preview search notes, or exact-title lookup suggestions
- candidate scoring shards
- staged paper-reading bundles under `.tmp/read_pool/<run_id>/<bibkey>/draft/`, reader provenance, reviewer findings, figure/table notes, formula uncertainty notes, or availability-source notes
- reports under `.battery/jobs/<job-id>/sidecars/` or `/tmp/battery-v3-sidecar-*`

Forbidden sidecar actions:

- editing `candidates.jsonl`, `library.bib`, `preferences.yml`, `topic.yml`, `papers/<bibkey>/metadata.yml`, PDFs, or generated HTML
- running `battery_lit collect`, `tool dedup --fix`, `candidates apply-scores`, `acquire`, `promote`, or metadata/bibkey update concurrently against the same topic
- writing final `source_map.json`, `note_plan.json`, or `deep_read.json`
- reading sibling topic folders as examples or context

The main Codex operation worker should invoke project CLI controllers such as `read-many` for serialized topic mutations, then report the controller result. Do not merge multi-paper reading artifacts by hand.

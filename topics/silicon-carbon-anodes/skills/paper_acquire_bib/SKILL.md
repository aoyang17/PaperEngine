# paper_acquire_bib

Use this skill whenever the user asks to download PDFs, acquire papers, promote candidates, add papers to the library, or import one paper from another topic.

## Safety Rules

- Acquire only open-access PDFs.
- Do not directly edit `library.bib`.
- Do not move PDFs by shell command unless `battery_lit acquire` or `battery_lit promote` reports a blocker and the user approves a repair.
- DOI/arXiv are preferred identifiers, but OpenAlex Work ID, Semantic Scholar ID, DBLP key, or a verified publisher/work URL can identify papers that lack DOI/arXiv. ISSN/ISBN are venue/book metadata only; do not use them alone to pass citation guard.
- If title/year evidence or a paper-level verified source is missing, report a blocker instead of guessing.
- Prefer `battery_lit acquire CAND-ID`; if a manual PDF is needed, download it into a fresh temporary directory and remove that directory after `battery_lit acquire --manual-pdf`.
- For a cross-topic import, use `battery_lit library import-from-topic`; never shell-copy a paper, or directly edit `library.bib`, `candidates.jsonl`, PDFs, or paper directories.

## Cross-Topic Import

Use this path only when the user explicitly names the source topic path. Do not discover or inspect sibling topics to find a source.

1. If the user supplies a source bibkey, use it directly. If they supply a title instead, run the controlled source lookup `battery_lit library find --root <source-topic> --query "<title>" --json` and continue only when it returns exactly one match; otherwise ask the user to choose a bibkey.
2. Run exactly one import command:

```bash
battery_lit library import-from-topic --root <target-topic> --source-root <source-topic> --source-bibkey <bibkey> --json
```

3. Report `imported`, `already_exists`, or any skipped result clearly. An imported record is a target candidate with `status: in_library` and `decision: relevant`; `preferences.yml` is not refreshed immediately.

There is no web button or batch interface for cross-topic imports. Map natural-language requests such as "import this paper from another topic" to this skill.

## Workflow

For each candidate:

1. Inspect only the candidate record with `battery_lit candidates show --json`.
2. Run `battery_lit tool enrich-metadata --candidate CAND-ID --live --json`.
3. Run `battery_lit tool citation-guard --candidate CAND-ID --json`.
4. Run `battery_lit acquire CAND-ID`.
5. Run `battery_lit promote CAND-ID`.
6. Run `battery_lit bib check` and `battery_lit pdf check`.

If a PDF already exists, accept the tool's skip result and do not download it again.

## Temporary PDF Hygiene

Do not use fixed paths such as `/tmp/paper.pdf` or `/tmp/<task>/source.tar`.

For a manual open-access PDF handoff, use a temporary directory and clean it:

```bash
tmpdir=$(mktemp -d)
# download the approved open-access PDF to "$tmpdir/paper.pdf"
battery_lit acquire --root <topic> CAND-ID --manual-pdf "$tmpdir/paper.pdf"
rm -rf "$tmpdir"
```

Only remove the temporary directory you created for this handoff.

## Output to User

Report bibkeys promoted, PDFs skipped because they already existed, blockers, and the next deep-reading command.

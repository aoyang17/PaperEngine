# UI Productization Review

This note records the current Web UI productization pass against the plan in `.tmp/v3_ui_productization_plan.md`.

## Scope

- Kept the existing Python serverlet, Jinja templates, small JavaScript, and all action/session APIs.
- Changed visual presentation only for the Web workbench pages.
- Added user-facing reading-result structure and lightweight Zotero-compatible citation meta tags.

## Visual Checks

Generated browser screenshots in the workstation container with Playwright:

- `.tmp/ui-productization-real-screens/dashboard-desktop.png`
- `.tmp/ui-productization-real-screens/dashboard-mobile.png`
- `.tmp/ui-productization-real-screens/candidates-desktop.png`
- `.tmp/ui-productization-real-screens/library-desktop.png`
- `.tmp/ui-productization-real-screens/reading-result-desktop.png`
- `.tmp/ui-productization-real-screens/reading-result-mobile.png`

Compared visually against Paper Insight reference screenshots:

- Home/reference list style: `https://paper-insight.herobase.tech/`
- Conference list style: `https://paper-insight.herobase.tech/conference/iclr_2026`

## Iteration Notes

### Iteration 1: Visual System And Workbench Shell

- Added productized CSS tokens for canvas, surfaces, borders, shadows, primary orange, secondary blue, success, danger, and dismissed states.
- Polished the workbench topbar, metric cards, panels, and Codex Console.
- Kept Codex session protocol unchanged.

Visual result: the UI no longer reads as a raw backend/admin table. Codex Console remains visible but no longer dominates the main workspace.

### Iteration 2: List And Library Presentation

- Converted List and Library tables into card-like row layouts while preserving table semantics and existing JS controls.
- Candidate rows now use title-first hierarchy, source/year/venue chips, abstract disclosure, score badge, and clearer relevance controls.
- Library rows now use title-adjacent PDF/Knowledge chips and quieter secondary metadata.

Visual result: closer to Paper Insight's scannable paper-list feel, while staying denser and more operational for local workflows.

### Iteration 3: Reading Result And Final Visual Cohesion

- Added a first-screen skim layer with summary, why it matters, what to remember, read-depth guidance, and visual highlights.
- Preserved detailed sections for argument map, claims, method, typed paper lenses, evaluation, visuals, availability, extraction notes, and BibTeX.
- Added lightweight `citation_*` meta tags for Zotero-compatible metadata discovery.
- Kept internal reading plans, raw source IDs, and parser workflow metrics out of the user-facing page.

Visual result: reading output is now more layered and easier to scan before diving into details. Mobile tables are horizontally scrollable rather than compressed into unreadable columns.

## Remaining Visual-Only Polish Ideas

- Paper Insight still has a more refined conference-card aesthetic: softer card spacing, stronger title typography, and more colorful topical chips.
- Candidate and Library rows could later adopt larger title cards for relaxed browsing, but this would be a visual iteration only.
- Reading Result could later use more editorial section separators and a sticky table of contents, but this should not change the reading workflow.

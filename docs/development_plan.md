# Development Plan

## Goal

Build and maintain a serverlet-first literature workbench: the user starts `paper_engine start --base-dir` for first-time topic creation or `paper_engine start --root` for an existing topic, operates from the browser, and topic actions enter one persistent Codex operator session that calls `paper_engine` for state changes.

## Non-Drift Rules

- Default first-time user path is `paper_engine start --base-dir <parent-dir>` followed by browser topic creation and operation.
- External interactive Codex is only an advanced/debug fallback.
- Web handlers may render state and manage session/bootstrap state, but must not directly mutate candidate, library, PDF, metadata, or reading artifacts.
- The Codex operator must use `paper_engine` CLI commands for state-changing workflow steps.
- Topic files remain the source of truth.

## Current Phases

## Phase 1: Serverlet Entry

- Keep `paper_engine start --base-dir` as the documented first-time default and `start --root` for existing topics.
- Keep `paper_engine web serve` as compatibility only.
- Validate topic root before serving existing topics; do not require topic files for bootstrap mode.

## Phase 2: Codex Operation Kernel

- Keep one app-server backed Codex session per web workbench.
- Send chat messages and UI actions through `/api/session/*`.
- Use bounded prompt contracts for quick actions and table actions.
- Keep bootstrap/compatibility jobs available only where a persistent topic session does not exist yet.

## Phase 3: Browser Workbench

- Overview provides topic scope, health/recent-job visibility, and Total Paper/Candidate/Downloaded/Read Paper counters.
- The right-side Codex operator provides chat, model/effort selection, Search +30, Score Queue, and Work Status.
- List supports tabs, sorting, venue filtering, abstract expansion, preference marking, dismiss, and selected PDF download through session actions.
- Library supports title-adjacent PDF/Note links and selected paper reading through session actions.

## Phase 4: Verification

- Run focused tests for each changed module.
- Run full pytest before completion.
- Run render check with `scripts/check_web_render.py`.
- Run live Codex probe in a writable Codex runtime.

## Phase 5: Documentation

- User manuals describe browser/serverlet as the default workflow.
- Deployment docs document `paper_engine start`.
- Development status records verification evidence and known blockers.

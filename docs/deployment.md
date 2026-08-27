# Deployment

## Requirements

- Python 3.10 or newer.
- Codex CLI 0.144.0 or newer available on `PATH` for the persistent web operator session and bootstrap jobs.
- Network access for live paper search and open-access PDF acquisition.

Install the current compatible CLI and verify the version inside the same environment that runs the workbench:

```bash
npm install -g @openai/codex@0.144.1
codex --version
```

The browser defaults to GPT-5.6 Sol with medium reasoning. It also exposes GPT-5.6 Terra, GPT-5.6 Luna, GPT-5.5, GPT-5.3 Codex Spark, and the account default. Use environment variables only as a deployment/debug default when you do not want to choose in the browser:

```bash
export PAPER_ENGINE_CODEX_MODEL=gpt-5.6-sol
export PAPER_ENGINE_CODEX_EFFORT=medium
```

## Install From Source

From this repository:

```bash
python3 -m pip install -r requirements.txt -r requirements-dev.txt
python3 -m pip install -e .
```

For source-only use without installing:

```bash
bin/paper_engine status --root <topic> --json
```

The wrapper adds this repository's `src/` directory to `PYTHONPATH`.

Some containers disable Python user-site packages even after `python3 -m pip install --user ...`. If imports such as `jinja2`, `jsonschema`, or `pytest` still fail after installation, either install the project editable package into the active environment or export the user-site path explicitly:

```bash
export PYTHONPATH="$HOME/.local/lib/python3.10/site-packages:$PYTHONPATH"
```

Use the Python minor version that matches `python3 --version`.

## Create A Topic

The ordinary first-time path starts the workbench from a parent directory:

```bash
./bin/paper_engine start --base-dir /paper_hub --host 0.0.0.0 --port 10005
```

Create the topic in the browser. The init job uses Codex plus `paper_engine init --base-dir` and must not inspect sibling topic folders. If Codex, the selected model/effort, or the CLI fails, the Create Topic page shows the error in Recent Jobs.

For scripts or debugging, use the CLI directly:

```bash
./bin/paper_engine init --base-dir /paper_hub --title "<topic title>" --direction "<one paragraph research direction>"
```

Advanced/debug fallback for Codex-assisted topic refinement: attach the project README:

```text
@/<path-to-PaperEngine>/README.md
使用 paper_engine 工具，给我在 /paper_hub/ 下初始化一个新的 topic 目录。
名字定为 "<topic title>"。
检索方向是 <one paragraph research direction>.
```

The tool should use `bin/paper_engine init --base-dir <parent-dir> --title "<title>" --direction "<direction>"` and should not inspect sibling topic folders.

## Start The Serverlet Workbench

For first-time topic creation:

```bash
./bin/paper_engine start --base-dir /paper_hub --host 0.0.0.0 --port 10005
```

For an existing topic:

```bash
./bin/paper_engine start --root <topic> --host 0.0.0.0 --port 10005
```

By default, `paper_engine start` disables the Codex runtime sandbox for the serverlet process. This is intentional for Docker deployments where Codex workspace sandboxing can fail before `paper_engine` starts. Topic `policy.yml` and the CLI remain the safety boundary. Use `--codex-sandbox` only when you explicitly want to test Codex workspace sandboxing.

If running inside Docker, publish the port when starting the container, then browse to:

```text
http://<server-ip>:10005/dashboard.html
```

Use `--host 0.0.0.0` when accessing from another machine. `127.0.0.1` only accepts connections inside the same machine/container.

## Validate

```bash
python3 -m pytest -q
./bin/paper_engine policy check --root <topic> --json
./bin/paper_engine status --root <topic> --json
./bin/paper_engine bib check --root <topic>
./bin/paper_engine pdf check --root <topic>
```

Optional probes:

```bash
python3 scripts/check_web_render.py --root <topic>
PAPER_ENGINE_LIVE_CODEX=1 python3 scripts/run_live_codex_probe.py --root <topic>
PAPER_ENGINE_LIVE_CODEX=1 python3 scripts/run_live_web_flow_probe.py --model gpt-5.6-sol --effort medium
```

For release-level validation, "live testing" means the full browser user journey in `docs/live_testing.md`: create topic from UI, search real candidates, mark relevant/irrelevant/dismissed, download at least one real PDF, read at least one paper, and inspect saved UI screenshots.

Canonical live test command:

```bash
PYTHONPATH=/home/battery/.local/lib/python3.10/site-packages:src python3 scripts/run_live_user_journey_e2e.py
```

## Safety Model

- Topic files are the source of truth.
- The browser workbench is the ordinary user interface.
- UI actions and chat messages enter one persistent Codex operator session after a topic is bound.
- The Codex operator calls `paper_engine` for state-changing work.
- The web server reads topic state and stores job logs, but should not directly edit candidate, library, PDF, or reading artifacts.

## Troubleshooting

- Browser cannot connect: use `--host 0.0.0.0`, confirm Docker was started with `-p <host-port>:<container-port>`, and browse to the server IP rather than `127.0.0.1` from another machine.
- Codex missing or too old: run `codex --version` inside the same container/session that starts the web workbench and install Codex CLI 0.144.0 or newer.
- Persistent session unavailable: choose Account default/default first, then check `codex app-server --help` in the same container/session.
- Bootstrap or compatibility job stuck: inspect `.paper_engine/active_job.json`, `.paper_engine/jobs/<job_id>/events.jsonl`, `.paper_engine/jobs/<job_id>/stderr.log`, and `.paper_engine/jobs/<job_id>/summary.json`.
- Model or effort unsupported: choose Account default/default in the browser, or unset `PAPER_ENGINE_CODEX_MODEL` and `PAPER_ENGINE_CODEX_EFFORT`.
- Dependency missing: rerun `python3 -m pip install -r requirements.txt -r requirements-dev.txt`; if the container disables user-site packages, add the installed user-site directory to `PYTHONPATH` or install the package editable into the active environment.
- Search backend unavailable: check `bin/paper-search` and `requirements-backend.txt`; reinstall backend dependencies if the search job reports import errors.
- Stale state: run `paper_engine policy check --root <topic> --json` and `paper_engine status --root <topic> --json`.

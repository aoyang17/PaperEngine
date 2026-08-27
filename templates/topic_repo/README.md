# {title}

This is a PaperEngine topic repository.

Use the browser workbench as the daily entry point:

```bash
paper_engine start --root <topic> --host 0.0.0.0 --port 10005
```

Codex operation jobs enter this topic by following `skills/topic_enter/SKILL.md`: read `AGENTS.md`, `policy.yml`, `topic.yml`, and `preferences.yml`, then use `paper_engine policy check` and `paper_engine status`.

Do not read `library.bib`, `candidates.jsonl`, or `papers/*` in full by default. Use `paper_engine` summary commands first.

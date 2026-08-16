# {title}

This is a battery Research Literature topic repository.

Use the browser workbench as the daily entry point:

```bash
battery_lit start --root <topic> --host 0.0.0.0 --port 10005
```

Codex operation jobs enter this topic by following `skills/topic_enter/SKILL.md`: read `AGENTS.md`, `policy.yml`, `topic.yml`, and `preferences.yml`, then use `battery_lit policy check` and `battery_lit status`.

Do not read `library.bib`, `candidates.jsonl`, or `papers/*` in full by default. Use `battery_lit` summary commands first.

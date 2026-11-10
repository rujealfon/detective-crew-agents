# Benchmarks

Method for comparing models and effort levels for a crew role, and the trials
run so far.

## Trials

- [Sonnet versus Opus fixer trial, 2026-10-28](sonnet-opus-2026-10-28.md)
- [Terra versus Sol fixer trial, 2026-10-28](terra-sol-2026-10-28.md)
- [Inspector and runner effort trials, 2026-11-11](inspector-runner-2026-11-11.md)

All are seeded smoke runs and say little about harder, unseeded work. In the
inspector and runner trials every arm scored perfectly, so the current settings
stay; a trial that separates the inspector arms needs harder seeds.

## Harness

[`tools/benchmark-fixer.py`](../tools/benchmark-fixer.py) is the existing
harness. It seeds five single-line regressions into `tools/session-usage.py`,
checks that the untouched test suite passes on the baseline and fails on every
seed, then runs each candidate model once per case in a fresh temporary
workspace with the fixer instructions. `--provider` selects `codex` or `claude`,
and `--dry-run` validates the baseline and seeds without model calls. It currently
hardcodes medium effort (`--effort medium` for Claude, `model_reasoning_effort`
for Codex) and records no cost field, only elapsed time and reported token
usage, so a multi-effort trial needs the effort made a parameter first.

[`tools/benchmark-inspector.py`](../tools/benchmark-inspector.py) and
[`tools/benchmark-runner.py`](../tools/benchmark-runner.py) take the model and
effort per arm, record the CLI-reported cost, and score a fenced JSON verdict.
Both offer `--dry-run`, `--repeats`, `--limit` and `--output`.

## Method for a model or effort trial

1. Use real tasks, each with an outcome check such as a failing test, a build,
   or a script that decides pass or fail without a reader's judgment.
2. Run each candidate at two or three effort levels. Run every attempt in its
   own fresh session so prompt caches are not shared between candidates.
3. Record the cost per finished task from the session's usage, not the price
   per token. A cheaper model that needs retries can cost more per result.
4. Report the hardest tasks separately. A few of them dominate spend, and an
   average hides whether a candidate fails exactly where it matters.
5. Keep a multi-model setup only if it beats every single-model point on cost
   per finished task at equal or better pass rate.
6. Shadow-run the winner on live work, without changing defaults, before
   switching the defaults.

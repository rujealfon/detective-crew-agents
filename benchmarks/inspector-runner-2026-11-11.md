# Inspector and runner effort trials — 2026-11-11

Recommendation: keep `inspector` on Sonnet 5.5 at high and `runner` on Haiku 5.5
at low. Every arm scored perfectly in both trials, so neither shows a quality
gain from more effort or a bigger model. The seeds were too easy to separate the
inspector arms, and the inspector cost difference between medium and high was
about 6%, so dropping to medium saves little against an unmeasured risk on
harder reviews.

Both trials ran on the local Claude Code CLI (2.1.322, Claude login). Each run
was a fresh `claude -p` process in a fresh temporary workspace, with the agent's
instructions (frontmatter stripped) written as `CLAUDE.md`, project settings
only, no session persistence, slash commands disabled, and tools limited to
Read, Glob and Grep with Agent, Bash, Edit and Write disallowed. Arm or effort
order alternated per case and repeat. Every answer ended with a fenced JSON
verdict that the harness scored; a missing or invalid verdict would count as
`unparsed`, and none occurred. Cost is the CLI-reported `total_cost_usd`, not
billed cost. Prompt caching was not controlled.

## Inspector

[`tools/benchmark-inspector.py`](../tools/benchmark-inspector.py), two repeats.
Ten cases on `tools/session-usage.py`: the five single-line seeds from the fixer
trial, three subtler ones (a `>` to `>=` range check, a lost inclusive bound,
and an `and` to `or` guard), and two clean refactors that keep the suite
passing. The prompt presented each `change.diff` with its requirement and never
said a defect existed. A defect counts as caught when the verdict names the file
and a line within three of the seeded line; a clean case is correct when the
verdict reports no defect.

| Arm | Defects caught | Clean correct | Seconds | Cost USD | Cost per caught defect |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sonnet 5.5, medium | 16/16 | 4/4 | 228.1 | 1.41 | 0.088 |
| Sonnet 5.5, high | 16/16 | 4/4 | 262.2 | 1.49 | 0.093 |
| Opus 5.5, medium | 16/16 | 4/4 | 311.1 | 2.14 | 0.133 |

Every arm caught every defect in both repeats and raised no false positive on
the clean refactors. Sonnet at medium was 13% faster and 5% cheaper than at
high; Opus at medium cost about 1.5 times as much as Sonnet at high. A trial
that can separate the arms needs harder seeds: multi-line or cross-file defects,
missing validation, or a defect the diff's own tests do not cover.

## Runner

[`tools/benchmark-runner.py`](../tools/benchmark-runner.py), two repeats. Twelve
lookups on a `git archive` snapshot of this repository, with answers computed
from the snapshot: three function definitions with few matches, three whose
names also appear in other files, two agent `model:` lines, two config lines,
and two questions that need the enclosing function of a matching line. Correct
means the exact file and a line within one.

| Effort | Correct | Unparsed | Seconds | Cost USD |
| --- | ---: | ---: | ---: | ---: |
| low | 24/24 | 0 | 146.0 | 0.035 |
| medium | 24/24 | 0 | 160.4 | 0.039 |

Medium added no accuracy and cost about 10% more time and money. A first smoke
run showed one low-effort answer as unparsed; that was a harness bug that
paired an earlier code fence with the verdict fence, fixed before this run.

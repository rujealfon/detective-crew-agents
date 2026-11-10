#!/usr/bin/env python3
"""Run a local, seeded inspector review benchmark; requires Python 3.9+ and the Claude Code CLI."""
import argparse
import difflib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('benchmark_fixer', ROOT / 'tools/benchmark-fixer.py')
fixer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixer)

TARGET, TEST = fixer.TARGET, fixer.TEST
NOTICE = ('Seeded review benchmark, not a measure of real review quality. '
          'API token prices are not billed cost; any cost shown is the CLI-reported figure for these runs only.')
ARMS = {
    'sonnet-medium': ('claude-sonnet-5-5', 'medium'),
    'sonnet-high': ('claude-sonnet-5-5', 'high'),
    'opus-medium': ('claude-opus-5-5', 'medium'),
}
LINE_TOLERANCE = 3
CLEAN_REQUIREMENT = 'Refactor without changing behavior.'
FORMAT_INSTRUCTION = ('End your review with a fenced json block exactly of the form '
                      '{"defect_found": true|false, "file": "<path or null>", "line": <int or null>}, '
                      'naming the single most important defect (file and line in the changed file), '
                      'or defect_found false when you find none.')

# Cases: (id, kind, requirement, old, new). Each anchor must occur exactly once in the baseline.
# Defect seeds must fail the untouched suite; clean diffs must pass it.
CASES = tuple((m[0], 'defect', m[1], m[2], m[3]) for m in fixer.MUTATIONS) + (
    ('single-turn-range', 'defect', 'A range whose first and last turn are the same turn must be accepted.',
     'if left > right:', 'if left >= right:'),
    ('creation-boundary', 'defect', 'Agents created exactly at the range start or end belong to the selected range.',
     'created_in_range = start <= timestamp(agent["created_at"]) <= end',
     'created_in_range = start < timestamp(agent["created_at"]) <= end'),
    ('legacy-only-files', 'defect', 'Only files with cumulative counters and no per-response usage are reported as legacy.',
     'if has_legacy and not has_usage:', 'if has_legacy or not has_usage:'),
    ('clean-rename-local', 'clean', CLEAN_REQUIREMENT,
     '    end = None\n    seconds = 0.0\n    for start, stop in sorted(intervals):\n'
     '        if end is None or start > end:\n            seconds += (stop - start).total_seconds()\n'
     '        elif stop > end:\n            seconds += (stop - end).total_seconds()\n'
     '        end = max(end, stop) if end else stop\n    return seconds\n',
     '    end = None\n    total = 0.0\n    for start, stop in sorted(intervals):\n'
     '        if end is None or start > end:\n            total += (stop - start).total_seconds()\n'
     '        elif stop > end:\n            total += (stop - end).total_seconds()\n'
     '        end = max(end, stop) if end else stop\n    return total\n'),
    ('clean-extract-local', 'clean', CLEAN_REQUIREMENT,
     '    result["uncached_input_tokens"] = result["input_tokens"] - result["cached_input_tokens"]\n',
     '    cached = result["cached_input_tokens"]\n    result["uncached_input_tokens"] = result["input_tokens"] - cached\n'),
)


def build_case(case, source):
    """Return (mutated bytes, unified diff text, first changed line in the mutated file) or raise ValueError."""
    old, new = case[3].encode(), case[4].encode()
    if source.count(old) != 1:
        raise ValueError('anchor must occur exactly once')
    mutated = source.replace(old, new)
    before, after = source.decode().splitlines(True), mutated.decode().splitlines(True)
    diff = ''.join(difflib.unified_diff(before, after, fromfile='a/' + TARGET, tofile='b/' + TARGET))
    line = next(i for i, (x, y) in enumerate(zip(before, after), 1) if x != y)
    return mutated, diff, line


def make_prompt(requirement):
    return (f'Review the change in change.diff to {TARGET} against this requirement: {requirement} '
            f'The test results were not run. The baseline is the "a/" side of the diff. {FORMAT_INSTRUCTION}')


def arm_order(arms, case_index, repeat):
    """Reverse the arm order on alternate (case, repeat) slots to spread position bias."""
    return list(arms) if (case_index + repeat) % 2 == 0 else list(reversed(arms))


def fenced_blocks(text):
    """Return fenced code block bodies, pairing each opening fence with its own close."""
    blocks, current = [], None
    for line in text.splitlines():
        stripped = line.strip()
        if current is None:
            if stripped.startswith('```'):
                current = []
        elif stripped == '```':
            blocks.append('\n'.join(current))
            current = None
        else:
            current.append(line)
    return blocks


def parse_verdict(text):
    """Return the verdict dict from the last fenced json block, or None when unparseable."""
    if not isinstance(text, str):
        return None
    for block in reversed(fenced_blocks(text)):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if isinstance(data, dict) and type(data.get('defect_found')) is bool:
            return data
    return None


def score(kind, verdict, expected_line):
    """Return caught/missed for defect cases, correct/false_positive for clean ones, unparsed without a verdict."""
    if verdict is None:
        return 'unparsed'
    found = verdict['defect_found']
    if kind == 'clean':
        return 'false_positive' if found else 'correct'
    line, name = verdict.get('line'), verdict.get('file')
    hit = (found and isinstance(name, str) and name.replace('\\', '/').endswith('session-usage.py')
           and type(line) is int and abs(line - expected_line) <= LINE_TOLERANCE)
    return 'caught' if hit else 'missed'


def result_event(path):
    found = None
    for line in path.read_text(errors='replace').splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get('type') == 'result':
            found = event
    return found


def run_case(arm, case, source, tests, diff, expected_line, instructions, artifact, timeout):
    model, effort = ARMS[arm]
    artifact.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='inspector-task-') as temporary:
        directory = Path(temporary)
        mutated = source.replace(case[3].encode(), case[4].encode())
        fixer.populate(directory, mutated, tests, instructions, 'CLAUDE.md')
        (directory / 'change.diff').write_text(diff)
        requirement = case[2]
        command = ['claude', '-p', make_prompt(requirement), '--model', model, '--effort', effort,
                   '--output-format', 'stream-json', '--verbose', '--no-session-persistence',
                   '--setting-sources', 'project', '--disable-slash-commands',
                   '--tools', 'Read,Glob,Grep', '--allowedTools', 'Read,Glob,Grep',
                   '--disallowedTools', 'Agent,Bash,Edit,Write']
        events = artifact / 'events.jsonl'
        result = fixer.execute(command, directory, timeout, events, artifact / 'stderr.log')
    usage, errors = fixer.claude_usage(events)
    final = result_event(events)
    text = final.get('result') if final else None
    cost = final.get('total_cost_usd') if final else None
    verdict = parse_verdict(text)
    if result['error'] or result['timed_out'] or result['exit_code'] != 0 or errors or not usage:
        status = 'infrastructure_error'
    else:
        status = score(case[1], verdict, expected_line)
    record = {'arm': arm, 'model': model, 'effort': effort, 'case': case[0], 'kind': case[1],
              'expected_line': expected_line, 'status': status, 'seconds': result['duration_seconds'],
              'usage': usage, 'total_cost_usd': cost if isinstance(cost, (int, float)) else None,
              'verdict': verdict, 'exit_code': result['exit_code'], 'timed_out': result['timed_out']}
    (artifact / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def summarize(runs, arms):
    totals = {}
    for arm in arms:
        mine = [r for r in runs if r['arm'] == arm]
        defects = [r for r in mine if r['kind'] == 'defect']
        clean = [r for r in mine if r['kind'] == 'clean']
        caught = sum(r['status'] == 'caught' for r in defects)
        costs = [r['total_cost_usd'] for r in mine if r['total_cost_usd'] is not None]
        cost = round(sum(costs), 4) if costs else None
        totals[arm] = {
            'defects_caught': caught, 'defects_total': len(defects),
            'clean_correct': sum(r['status'] == 'correct' for r in clean), 'clean_total': len(clean),
            'unparsed': sum(r['status'] == 'unparsed' for r in mine),
            'infrastructure_errors': sum(r['status'] == 'infrastructure_error' for r in mine),
            'total_seconds': round(sum(r['seconds'] for r in mine), 1),
            'total_cost_usd': cost,
            'cost_per_caught_defect_usd': round(cost / caught, 4) if cost is not None and caught else None}
    per_case = {}
    for r in runs:
        per_case.setdefault(r['case'], {}).setdefault(r['arm'], []).append(r['status'])
    return {'arms': totals, 'cases': per_case}


def render_markdown(summary, valid):
    arms = summary['summary']['arms']
    lines = [NOTICE, '', f'Case validation: {"passed" if valid else "FAILED"}', '',
             '| Arm | Defects caught | Clean correct | Unparsed | Infra errors | Seconds | Cost USD | Cost per caught defect |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for arm, t in arms.items():
        lines.append(f"| {arm} | {t['defects_caught']}/{t['defects_total']} | {t['clean_correct']}/{t['clean_total']} | "
                     f"{t['unparsed']} | {t['infrastructure_errors']} | {t['total_seconds']} | "
                     f"{t['total_cost_usd']} | {t['cost_per_caught_defect_usd']} |")
    names = list(arms)
    lines += ['', '| Case | ' + ' | '.join(names) + ' |', '| --- |' + ' --- |' * len(names)]
    for case, by_arm in summary['summary']['cases'].items():
        lines.append(f'| {case} | ' + ' | '.join(', '.join(by_arm.get(a, [])) or '-' for a in names) + ' |')
    return '\n'.join(lines) + '\n'


def resolve_output(path):
    """Return the resolved output path, or None when it lies inside the repository."""
    output = path.expanduser().resolve()
    return None if output.is_relative_to(ROOT) else output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--arms', nargs='+', choices=sorted(ARMS), default=list(ARMS))
    parser.add_argument('--limit', type=int, help='run only the first N cases')
    parser.add_argument('--timeout', type=float, default=300)
    parser.add_argument('--output', type=Path, help='new output directory outside this repository (default: temporary directory)')
    parser.add_argument('--dry-run', action='store_true', help='validate baseline and every case without model calls')
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    if args.repeats < 1 or (args.limit is not None and args.limit < 1):
        parser.error('--repeats and --limit must be at least 1')
    if args.output:
        output = resolve_output(args.output)
        if output is None:
            parser.error('--output must be outside the repository')
        output.mkdir(parents=True, exist_ok=False)
    else:
        output = Path(tempfile.mkdtemp(prefix='inspector-benchmark-'))
    print(f'Artifacts: {output}', flush=True)
    source, tests = (ROOT / TARGET).read_bytes(), (ROOT / TEST).read_bytes()
    body = re.sub(r'\A---\n.*?\n---\n', '', (ROOT / 'claude/inspector.md').read_text(), count=1, flags=re.S).lstrip('\n')
    instructions = (body + '\nWork directly. Do not delegate or spawn subagents.\n').encode()
    summary = {'notice': NOTICE, 'arms': {a: ARMS[a] for a in args.arms}, 'dry_run': args.dry_run,
               'validation': [], 'runs': []}
    baseline = fixer.evaluate(source, tests, output / 'baseline')
    summary['baseline'] = baseline
    valid = baseline['exit_code'] == 0 and not baseline['error'] and not baseline['timed_out']
    built = []
    for case in CASES:
        try:
            mutated, diff, line = build_case(case, source)
        except ValueError as error:
            summary['validation'].append({'case': case[0], 'error': str(error)})
            valid = False
            continue
        check = fixer.evaluate(mutated, tests, output / ('case-' + case[0]))
        expected_exit = 1 if case[1] == 'defect' else 0
        ok = check['exit_code'] == expected_exit and not check['error'] and not check['timed_out']
        summary['validation'].append({'case': case[0], 'kind': case[1], 'line': line, 'valid': ok, **check})
        valid = valid and ok
        built.append((case, diff, line))
    if valid and not args.dry_run:
        selected = built[:args.limit]
        for repeat in range(args.repeats):
            for index, (case, diff, line) in enumerate(selected):
                for arm in arm_order(args.arms, index, repeat):
                    print(f'{case[0]} r{repeat + 1}: {arm}', flush=True)
                    summary['runs'].append(run_case(arm, case, source, tests, diff, line, instructions,
                                                    output / f'{index + 1}-{case[0]}-{arm}-r{repeat + 1}', args.timeout))
    summary['summary'] = summarize(summary['runs'], args.arms)
    summary['infrastructure_failure'] = not valid or any(r['status'] == 'infrastructure_error' for r in summary['runs'])
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (output / 'summary.md').write_text(render_markdown(summary, valid))
    if args.dry_run or not valid:
        for item in summary['validation']:
            print(f"{item['case']}: {'ok' if item.get('valid') else 'INVALID'}"
                  f" ({item.get('kind', '?')}, line {item.get('line', '?')}, suite exit {item.get('exit_code', '?')})"
                  + (f" {item['error']}" if item.get('error') else ''))
    print(NOTICE)
    print(f'Summary: {output / "summary.md"}')
    return 2 if summary['infrastructure_failure'] else 0


if __name__ == '__main__':
    sys.exit(main())

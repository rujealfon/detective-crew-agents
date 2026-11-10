#!/usr/bin/env python3
"""Run a local lookup benchmark for the Claude runner agent across effort levels; requires Python 3.9+ and the Claude Code CLI."""
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('benchmark_fixer', ROOT / 'tools/benchmark-fixer.py')
fixer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixer)
execute, claude_usage = fixer.execute, fixer.claude_usage

MODEL = 'claude-haiku-5-5'
NOTICE = ('Seeded lookup benchmark on one repository snapshot, not a measure of real task quality. '
          'Cost is the CLI-reported total_cost_usd when present; it is not billed cost.')
SOURCES = ('install-agents.py', 'tools/session-usage.py', 'tools/benchmark-fixer.py')
SKIP_DIRS = ('.git', '__pycache__', 'node_modules')


def digest(name):
    return hashlib.sha256(name.encode()).hexdigest()


def read_lines(snapshot, relative):
    return (snapshot / relative).read_text().splitlines()


def text_files(snapshot):
    for path in sorted(snapshot.rglob('*')):
        if path.is_file() and not path.is_symlink() and not any(
                part in SKIP_DIRS for part in path.relative_to(snapshot).parts):
            try:
                yield str(path.relative_to(snapshot)), path.read_text().splitlines()
            except (UnicodeDecodeError, OSError):
                continue


def find_line(snapshot, relative, pattern, occurrence=0):
    """Return the 1-based line of the nth line in a file matching a regex, failing if it is absent."""
    hits = [number for number, line in enumerate(read_lines(snapshot, relative), 1) if re.search(pattern, line)]
    if len(hits) <= occurrence:
        raise ValueError(f'{pattern!r} not found in {relative}')
    return hits[occurrence]


def definitions(snapshot):
    """Map function name to a list of (file, def line, enclosing-def-lookup) across all snapshot Python files."""
    found = {}
    for relative, _ in text_files(snapshot):
        if not relative.endswith('.py'):
            continue
        try:
            tree = ast.parse((snapshot / relative).read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.setdefault(node.name, []).append((relative, node.lineno))
    return found


def enclosing_def(snapshot, relative, needle):
    """The def line of the single function containing every line that includes needle."""
    tree = ast.parse((snapshot / relative).read_text())
    lines = read_lines(snapshot, relative)
    hits = [number for number, line in enumerate(lines, 1) if needle in line]
    owners = set()
    for number in hits:
        best = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno <= number <= node.end_lineno:
                if best is None or node.lineno > best.lineno:
                    best = node
        if best is None:
            raise ValueError(f'{needle!r} is outside any function in {relative}')
        owners.add(best.lineno)
    if len(owners) != 1:
        raise ValueError(f'{needle!r} must occur in exactly one function of {relative}')
    return owners.pop()


def agent_model_line(snapshot, agent):
    return find_line(snapshot, f'claude/{agent}.md', r'^model:')


def build_questions(snapshot):
    """Compute every question and its answer from the snapshot; nothing is hardcoded by line number."""
    snapshot = Path(snapshot)
    defs = definitions(snapshot)
    contents = dict(text_files(snapshot))
    easy, ambiguous = [], []
    for name, places in defs.items():
        if len(places) != 1 or places[0][0] not in SOURCES or name.startswith('__'):
            continue
        pattern = re.compile(r'\b' + re.escape(name) + r'\b')
        other = sum(1 for path, lines in contents.items() if path != places[0][0]
                    for line in lines if pattern.search(line))
        total = other + sum(1 for line in contents[places[0][0]] if pattern.search(line))
        if other >= 2 and total >= 4:
            ambiguous.append(name)
        elif total <= 3:
            easy.append(name)
    easy.sort(key=digest)
    ambiguous.sort(key=digest)
    if len(easy) < 3 or len(ambiguous) < 3:
        raise ValueError('snapshot has too few candidate functions for the question set')
    questions = []

    def add(kind, question, file, line):
        questions.append({'id': f'q{len(questions) + 1:02d}', 'kind': kind, 'question': question,
                          'file': file, 'line': line})

    for kind, names in (('function-easy', easy[:3]), ('function-ambiguous', ambiguous[:3])):
        for name in names:
            file, line = defs[name][0]
            add(kind, f'Which file and line defines the Python function `{name}` (the `def` line)? '
                      f'It is defined in install-agents.py or in a file under tools/.', file, line)
    agents = sorted(path.stem for path in (snapshot / 'claude').glob('*.md'))
    agents = sorted(agents, key=digest)[:2]
    for agent in agents:
        add('agent-model', f'In the Claude crew, which file sets the model for the agent named `{agent}`, '
                           f'and at which line does the `model:` setting appear?',
            f'claude/{agent}.md', agent_model_line(snapshot, agent))
    add('config', 'Which line of package.json holds the package version?', 'package.json',
        find_line(snapshot, 'package.json', r'^\s*"version"\s*:'))
    add('two-hop', 'Some code in install-agents.py exits with a message containing "Unrecognized existing". '
                   'Which file and line holds the `def` of the function that contains that code?',
        'install-agents.py', enclosing_def(snapshot, 'install-agents.py', 'Unrecognized existing'))
    add('two-hop', 'In tools/benchmark-fixer.py, which function kills the whole process group with SIGKILL '
                   'when a command times out? Give the file and the line of its `def`.',
        'tools/benchmark-fixer.py', enclosing_def(snapshot, 'tools/benchmark-fixer.py', 'os.killpg'))
    add('config', 'In claude/runner.md, at which line is `maxTurns` set?', 'claude/runner.md',
        find_line(snapshot, 'claude/runner.md', r'^maxTurns:'))
    return questions


def export_snapshot(destination):
    """Export HEAD into destination so the answers cannot move during the run; hide the repo's own instructions."""
    archive = destination.with_suffix('.tar')
    with archive.open('wb') as out:
        subprocess.run(['git', '-C', str(ROOT), 'archive', 'HEAD'], stdout=out, check=True)
    destination.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(destination)
    archive.unlink()
    body = re.sub(r'\A---\n.*?\n---\n', '', (ROOT / 'claude/runner.md').read_text(), count=1, flags=re.S).lstrip('\n')
    (destination / 'CLAUDE.md').write_text(body + '\nWork directly. Do not delegate or spawn subagents.\n')
    agents = destination / 'AGENTS.md'
    if agents.exists():
        agents.unlink()
    return destination


def build_prompt(question):
    return (f'{question}\n\nAnswer using only read-only search and file reads. '
            'End your answer with a fenced json block of exactly this shape, with a path relative to the '
            'repository root and a 1-based line number:\n```json\n{"file": "relative/path", "line": 123}\n```')


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


def parse_answer(text):
    """Return (file, line) from the last fenced json block, or None when the answer is unparsed."""
    blocks = fenced_blocks(text or '')
    for block in reversed(blocks):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if not isinstance(data, dict):
            continue
        file, line = data.get('file'), data.get('line')
        if isinstance(file, str) and isinstance(line, int) and not isinstance(line, bool):
            return re.sub(r'^\./', '', file.strip()), line
        return None
    return None


def score(answer, question):
    if answer is None:
        return 'unparsed'
    file, line = answer
    return 'correct' if file == question['file'] and abs(line - question['line']) <= 1 else 'wrong'


def effort_order(efforts, question_index, repeat):
    """Rotate the effort order per question and repeat so no effort always runs first."""
    shift = (question_index + repeat) % len(efforts)
    return list(efforts[shift:]) + list(efforts[:shift])


def result_event(path):
    """Return the last stream-json result event, or an empty dict."""
    last = {}
    for line in path.read_text(errors='replace').splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get('type') == 'result':
            last = event
    return last


def run_question(question, effort, snapshot, artifact, timeout, model=MODEL):
    artifact.mkdir(parents=True)
    command = ['claude', '-p', build_prompt(question['question']), '--model', model, '--effort', effort,
               '--output-format', 'stream-json', '--verbose', '--no-session-persistence',
               '--setting-sources', 'project', '--disable-slash-commands',
               '--tools', 'Read,Glob,Grep', '--allowedTools', 'Read,Glob,Grep',
               '--disallowedTools', 'Agent,Bash,Edit,Write']
    result = execute(command, snapshot, timeout, artifact / 'events.jsonl', artifact / 'stderr.log')
    usage, errors = claude_usage(artifact / 'events.jsonl')
    event = result_event(artifact / 'events.jsonl')
    text = event.get('result') if isinstance(event.get('result'), str) else ''
    answer = parse_answer(text)
    cost = event.get('total_cost_usd')
    result.update(question=question['id'], effort=effort, model=model, usage=usage, event_errors=errors,
                  answer=None if answer is None else {'file': answer[0], 'line': answer[1]},
                  expected={'file': question['file'], 'line': question['line']},
                  outcome=score(answer, question),
                  cost_usd=cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None,
                  seconds=result['duration_seconds'])
    infra = result['error'] or result['timed_out'] or result['exit_code'] != 0 or bool(errors)
    result['infrastructure_error'] = bool(infra)
    (artifact / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def summarize(runs, efforts, questions):
    per_effort = {}
    for effort in efforts:
        mine = [r for r in runs if r['effort'] == effort]
        correct = sum(r['outcome'] == 'correct' for r in mine)
        costs = [r['cost_usd'] for r in mine]
        total_cost = None if not mine or any(c is None for c in costs) else round(sum(costs), 6)
        per_effort[effort] = {
            'runs': len(mine), 'correct': correct,
            'accuracy': round(correct / len(mine), 4) if mine else None,
            'unparsed': sum(r['outcome'] == 'unparsed' for r in mine),
            'infrastructure_errors': sum(r['infrastructure_error'] for r in mine),
            'total_seconds': round(sum(r['seconds'] for r in mine), 3),
            'total_cost_usd': total_cost,
            'cost_per_correct_usd': round(total_cost / correct, 6) if total_cost is not None and correct else None}
    table = []
    for question in questions:
        row = {'id': question['id'], 'kind': question['kind'], 'file': question['file'], 'line': question['line']}
        for effort in efforts:
            mine = [r for r in runs if r['question'] == question['id'] and r['effort'] == effort]
            row[effort] = f"{sum(r['outcome'] == 'correct' for r in mine)}/{len(mine)}"
        table.append(row)
    return per_effort, table


def render_markdown(summary, efforts):
    lines = [NOTICE, '', f"Model: {summary['model']}  Repeats: {summary['repeats']}", '',
             '| Effort | Runs | Correct | Accuracy | Unparsed | Infra errors | Seconds | Cost USD | Cost per correct USD |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for effort, s in summary['per_effort'].items():
        lines.append(f"| {effort} | {s['runs']} | {s['correct']} | {s['accuracy']} | {s['unparsed']} | "
                     f"{s['infrastructure_errors']} | {s['total_seconds']} | {s['total_cost_usd']} | "
                     f"{s['cost_per_correct_usd']} |")
    lines += ['', '| Question | Kind | Expected | ' + ' | '.join(efforts) + ' |',
              '| --- | --- | --- | ' + ' | '.join('---:' for _ in efforts) + ' |']
    for row in summary['questions']:
        lines.append(f"| {row['id']} | {row['kind']} | {row['file']}:{row['line']} | "
                     + ' | '.join(row[e] for e in efforts) + ' |')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--efforts', default='low,medium', help='comma-separated effort levels (default: low,medium)')
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--limit', type=int, help='run only the first N questions')
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--output', type=Path, help='new output directory outside this repository (default: temporary directory)')
    parser.add_argument('--dry-run', action='store_true', help='print all questions and answers without model calls')
    args = parser.parse_args(argv)
    efforts = [e.strip() for e in args.efforts.split(',') if e.strip()]
    if not efforts or len(set(efforts)) != len(efforts):
        parser.error('--efforts needs distinct, non-empty values')
    if args.repeats < 1:
        parser.error('--repeats must be at least 1')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be at least 1')
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    if args.output:
        output = args.output.expanduser().resolve()
        if output == ROOT or ROOT in output.parents:
            parser.error('--output must be outside the repository')
    else:
        output = None
    with tempfile.TemporaryDirectory(prefix='runner-snapshot-') as temporary:
        snapshot = export_snapshot(Path(temporary) / 'repo')
        questions = build_questions(snapshot)[:args.limit]
        if args.dry_run:
            for q in questions:
                print(f"{q['id']} [{q['kind']}] {q['question']}\n    -> {q['file']}:{q['line']}")
            return 0
        if output is None:
            output = Path(tempfile.mkdtemp(prefix='runner-benchmark-'))
        else:
            output.mkdir(parents=True, exist_ok=False)
        print(f'Artifacts: {output}', flush=True)
        runs = []
        for index, question in enumerate(questions):
            for repeat in range(args.repeats):
                for effort in effort_order(efforts, index, repeat):
                    print(f"{question['id']} repeat {repeat + 1}: {effort}", flush=True)
                    runs.append(run_question(question, effort, snapshot,
                                             output / 'runs' / f"{question['id']}-r{repeat + 1}-{effort}",
                                             args.timeout))
    per_effort, table = summarize(runs, efforts, questions)
    summary = {'notice': NOTICE, 'model': MODEL, 'efforts': efforts, 'repeats': args.repeats,
               'per_effort': per_effort, 'questions': table, 'runs': runs,
               'infrastructure_failure': any(r['infrastructure_error'] for r in runs)}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (output / 'summary.md').write_text(render_markdown(summary, efforts))
    print(NOTICE)
    print(f'Summary: {output / "summary.md"}')
    return 2 if summary['infrastructure_failure'] else 0


if __name__ == '__main__':
    sys.exit(main())

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('benchmark_runner', ROOT / 'tools/benchmark-runner.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def grep_line(path, pattern):
    return [n for n, line in enumerate(path.read_text().splitlines(), 1) if re.search(pattern, line)]


class SnapshotCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.snapshot = benchmark.export_snapshot(Path(cls.temporary.name) / 'repo')
        cls.questions = benchmark.build_questions(cls.snapshot)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()


class QuestionTests(SnapshotCase):
    def test_snapshot_hides_repo_instructions_and_uses_runner_body(self):
        self.assertFalse((self.snapshot / 'AGENTS.md').exists())
        text = (self.snapshot / 'CLAUDE.md').read_text()
        self.assertTrue(text.endswith('Work directly. Do not delegate or spawn subagents.\n'))
        self.assertNotIn('model: claude-haiku-5-5', text)
        self.assertIn('Answer the assigned question', text)

    def test_question_set_shape_and_determinism(self):
        self.assertEqual(len(self.questions), 12)
        self.assertEqual(self.questions, benchmark.build_questions(self.snapshot))
        self.assertEqual(len({q['id'] for q in self.questions}), 12)
        self.assertGreaterEqual(sum(q['kind'] == 'function-ambiguous' for q in self.questions), 2)
        for q in self.questions:
            self.assertTrue((self.snapshot / q['file']).is_file(), q)
            self.assertGreaterEqual(q['line'], 1)

    def test_function_answers_match_independent_grep(self):
        for q in self.questions:
            if not q['kind'].startswith('function'):
                continue
            name = re.search(r'`(\w+)`', q['question']).group(1)
            self.assertEqual(grep_line(self.snapshot / q['file'], rf'^\s*def {name}\('), [q['line']], q)
        ambiguous = [q for q in self.questions if q['kind'] == 'function-ambiguous']
        for q in ambiguous:
            name = re.search(r'`(\w+)`', q['question']).group(1)
            elsewhere = sum(len(grep_line(p, rf'\b{name}\b')) for p in self.snapshot.rglob('*.py')
                            if p != self.snapshot / q['file'])
            self.assertGreaterEqual(elsewhere, 2)

    def test_fixed_questions_match_independent_grep(self):
        by_text = {q['question']: q for q in self.questions}
        version = by_text['Which line of package.json holds the package version?']
        self.assertEqual(version['line'], grep_line(self.snapshot / 'package.json', r'"version"')[0])
        self.assertEqual(version['file'], 'package.json')
        models = [q for q in self.questions if q['kind'] == 'agent-model']
        self.assertEqual(len(models), 2)
        for q in models:
            self.assertEqual(q['line'], grep_line(self.snapshot / q['file'], r'^model:')[0])
            self.assertRegex(q['file'], r'^claude/\w+\.md$')
        unrecognized = grep_line(self.snapshot / 'install-agents.py', 'Unrecognized existing')
        main_def = grep_line(self.snapshot / 'install-agents.py', r'^def main\(')
        hop = next(q for q in self.questions if 'Unrecognized existing' in q['question'])
        self.assertEqual(hop['line'], main_def[0])
        self.assertTrue(all(n > hop['line'] for n in unrecognized))
        kill = next(q for q in self.questions if 'SIGKILL' in q['question'])
        self.assertEqual(kill['line'], grep_line(self.snapshot / 'tools/benchmark-fixer.py', r'^def execute\(')[0])

    def test_dry_run_prints_questions_without_model_calls(self):
        with patch.object(benchmark, 'execute') as run, patch('builtins.print') as printed:
            self.assertEqual(benchmark.main(['--dry-run', '--limit', '3']), 0)
        run.assert_not_called()
        self.assertEqual(printed.call_count, 3)


class ParsingTests(unittest.TestCase):
    def test_parse_answer(self):
        text = 'It is here.\n```json\n{"file": "./a/b.py", "line": 12}\n```\n'
        self.assertEqual(benchmark.parse_answer(text), ('a/b.py', 12))
        self.assertEqual(benchmark.parse_answer('```json\n{"file": "x", "line": 1}\n```\nmore\n'
                                                '```json\n{"file": "y", "line": 2}\n```'), ('y', 2))
        # A non-json fence before the answer must not shift fence pairing.
        self.assertEqual(benchmark.parse_answer('```python\ndef f():\n```\nfound\n'
                                                '```json\n{"file": "z", "line": 3}\n```'), ('z', 3))

    def test_unparsed_cases(self):
        for text in ('', None, 'no block', '```json\nnot json\n```', '```json\n{"file": "x", "line": "3"}\n```',
                     '```json\n{"file": "x", "line": true}\n```', '```json\n[1]\n```',
                     '```json\n{"file": "x"}\n```'):
            with self.subTest(text=text):
                self.assertIsNone(benchmark.parse_answer(text))

    def test_score_tolerates_one_line(self):
        q = {'file': 'a.py', 'line': 10}
        self.assertEqual(benchmark.score(('a.py', 10), q), 'correct')
        self.assertEqual(benchmark.score(('a.py', 9), q), 'correct')
        self.assertEqual(benchmark.score(('a.py', 11), q), 'correct')
        self.assertEqual(benchmark.score(('a.py', 12), q), 'wrong')
        self.assertEqual(benchmark.score(('b.py', 10), q), 'wrong')
        self.assertEqual(benchmark.score(None, q), 'unparsed')

    def test_effort_alternation(self):
        efforts = ['low', 'medium']
        firsts = [benchmark.effort_order(efforts, q, r)[0] for q in range(2) for r in range(2)]
        self.assertEqual(firsts, ['low', 'medium', 'medium', 'low'])
        for q in range(3):
            for r in range(3):
                self.assertEqual(sorted(benchmark.effort_order(efforts, q, r)), sorted(efforts))


class RunTests(unittest.TestCase):
    def test_run_question_scores_and_records_cost(self):
        question = {'id': 'q01', 'file': 'a.py', 'line': 5, 'question': 'Where?'}
        reply = {'type': 'result', 'is_error': False, 'usage': {'input_tokens': 3}, 'total_cost_usd': 0.01,
                 'result': 'ok\n```json\n{"file": "a.py", "line": 6}\n```'}

        def fake_execute(command, cwd, timeout, stdout, stderr):
            self.assertIn('--effort', command)
            self.assertEqual(command[command.index('--effort') + 1], 'low')
            self.assertEqual(command[command.index('--disallowedTools') + 1], 'Agent,Bash,Edit,Write')
            stdout.write_text(json.dumps(reply) + '\n')
            stderr.write_text('')
            return {'exit_code': 0, 'timed_out': False, 'error': None, 'duration_seconds': 2.0}
        with tempfile.TemporaryDirectory() as temporary, patch.object(benchmark, 'execute', side_effect=fake_execute):
            result = benchmark.run_question(question, 'low', Path(temporary), Path(temporary) / 'run', 10)
        self.assertEqual(result['outcome'], 'correct')
        self.assertEqual(result['cost_usd'], 0.01)
        self.assertFalse(result['infrastructure_error'])

    def test_missing_cost_is_null_and_summary(self):
        runs = [{'question': 'q01', 'effort': e, 'outcome': o, 'cost_usd': c, 'seconds': 1.0,
                 'infrastructure_error': False}
                for e, o, c in (('low', 'correct', 0.1), ('low', 'unparsed', 0.1), ('medium', 'correct', None))]
        per, table = benchmark.summarize(runs, ['low', 'medium'], [{'id': 'q01', 'kind': 'k', 'file': 'f', 'line': 1}])
        self.assertEqual(per['low']['accuracy'], 0.5)
        self.assertEqual(per['low']['unparsed'], 1)
        self.assertEqual(per['low']['cost_per_correct_usd'], 0.2)
        self.assertIsNone(per['medium']['total_cost_usd'])
        self.assertEqual(table[0]['low'], '1/2')

    def test_output_must_be_outside_repo(self):
        with patch.object(benchmark, 'execute') as run, self.assertRaises(SystemExit) as raised:
            benchmark.main(['--output', str(ROOT / 'tmp-benchmark-output')])
        self.assertEqual(raised.exception.code, 2)
        run.assert_not_called()
        self.assertFalse((ROOT / 'tmp-benchmark-output').exists())


if __name__ == '__main__':
    unittest.main()

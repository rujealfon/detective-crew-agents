import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('benchmark_inspector', ROOT / 'tools/benchmark-inspector.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class BenchmarkInspectorTests(unittest.TestCase):
    def test_real_cases_validate(self):
        source = (ROOT / bench.TARGET).read_bytes()
        tests = (ROOT / bench.TEST).read_bytes()
        kinds = [case[1] for case in bench.CASES]
        self.assertEqual((kinds.count('defect'), kinds.count('clean')), (8, 2))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.assertEqual(bench.fixer.evaluate(source, tests, directory / 'baseline')['exit_code'], 0)
            for case in bench.CASES:
                with self.subTest(case=case[0]):
                    mutated, diff, line = bench.build_case(case, source)
                    compile(mutated, bench.TARGET, 'exec')
                    self.assertIn('--- a/' + bench.TARGET, diff)
                    self.assertGreater(line, 0)
                    expected = 1 if case[1] == 'defect' else 0
                    self.assertEqual(bench.fixer.evaluate(mutated, tests, directory / case[0])['exit_code'], expected)

    def test_prompt_does_not_announce_a_defect(self):
        prompt = bench.make_prompt('Some requirement.')
        self.assertIn('Some requirement.', prompt)
        self.assertIn('The test results were not run.', prompt)
        self.assertNotIn('seeded', prompt.lower())
        self.assertNotIn('bug is', prompt.lower())

    def test_anchor_must_occur_once(self):
        with self.assertRaises(ValueError):
            bench.build_case(('x', 'defect', 'r', 'not present', 'y'), b'abc')

    def test_parse_verdict(self):
        good = 'Review text\n```json\n{"defect_found": true, "file": "tools/session-usage.py", "line": 12}\n```\n'
        self.assertEqual(bench.parse_verdict(good)['line'], 12)
        both = '```json\n{"defect_found": true}\n```\nlater\n```json\n{"defect_found": false}\n```'
        self.assertFalse(bench.parse_verdict(both)['defect_found'])
        # A non-json fence before the verdict must not shift fence pairing.
        mixed = ('```python\ndef f():\n```\nfindings\n'
                 '```json\n{"defect_found": true, "file": "tools/session-usage.py", "line": 196}\n```')
        self.assertEqual(bench.parse_verdict(mixed)['line'], 196)
        for bad in (None, '', 'no block', '```json\nnot json\n```', '```json\n{"defect_found": "yes"}\n```',
                    '```json\n[1]\n```'):
            with self.subTest(text=bad):
                self.assertIsNone(bench.parse_verdict(bad))

    def test_score_line_tolerance(self):
        def verdict(line, found=True, name='tools/session-usage.py'):
            return {'defect_found': found, 'file': name, 'line': line}
        self.assertEqual(bench.score('defect', verdict(100), 100), 'caught')
        self.assertEqual(bench.score('defect', verdict(103), 100), 'caught')
        self.assertEqual(bench.score('defect', verdict(97), 100), 'caught')
        self.assertEqual(bench.score('defect', verdict(104), 100), 'missed')
        self.assertEqual(bench.score('defect', verdict(96), 100), 'missed')
        self.assertEqual(bench.score('defect', verdict(None), 100), 'missed')
        self.assertEqual(bench.score('defect', verdict(100, name='other.py'), 100), 'missed')
        self.assertEqual(bench.score('defect', verdict(100, found=False), 100), 'missed')
        self.assertEqual(bench.score('defect', None, 100), 'unparsed')
        self.assertEqual(bench.score('clean', verdict(None, found=False), 5), 'correct')
        self.assertEqual(bench.score('clean', verdict(5), 5), 'false_positive')
        self.assertEqual(bench.score('clean', None, 5), 'unparsed')

    def test_arm_order_alternates(self):
        arms = ['a', 'b', 'c']
        self.assertEqual(bench.arm_order(arms, 0, 0), ['a', 'b', 'c'])
        self.assertEqual(bench.arm_order(arms, 1, 0), ['c', 'b', 'a'])
        self.assertEqual(bench.arm_order(arms, 0, 1), ['c', 'b', 'a'])
        self.assertEqual(bench.arm_order(arms, 1, 1), ['a', 'b', 'c'])

    def test_output_must_be_outside_repo(self):
        self.assertIsNone(bench.resolve_output(ROOT / 'out'))
        with self.assertRaises(SystemExit), patch('sys.stderr'):
            bench.main(['--dry-run', '--output', str(ROOT / 'inside-repo-benchmark')])
        self.assertFalse((ROOT / 'inside-repo-benchmark').exists())
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(bench.resolve_output(Path(temporary) / 'x'), (Path(temporary) / 'x').resolve())

    def test_dry_run_makes_no_model_calls(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(bench, 'run_case') as run:
            output = Path(temporary) / 'out'
            self.assertEqual(bench.main(['--dry-run', '--output', str(output)]), 0)
            run.assert_not_called()
            summary = json.loads((output / 'summary.json').read_text())
            self.assertEqual(len(summary['validation']), len(bench.CASES))
            self.assertTrue(all(item['valid'] for item in summary['validation']))

    def test_run_case_records_cost_and_scores(self):
        text = 'Found it.\n```json\n{"defect_found": true, "file": "tools/session-usage.py", "line": 197}\n```'
        events = [{'type': 'result', 'is_error': False, 'result': text, 'total_cost_usd': 0.25,
                   'usage': {'input_tokens': 3}}]
        case = bench.CASES[0]
        source = (ROOT / bench.TARGET).read_bytes()

        def fake_execute(command, cwd, timeout, stdout, stderr):
            self.assertEqual({p.name for p in cwd.rglob('*') if p.is_file()},
                             {'session-usage.py', 'test_session_usage.py', 'change.diff', 'CLAUDE.md'})
            self.assertEqual(command[command.index('--tools') + 1], 'Read,Glob,Grep')
            self.assertEqual(command[command.index('--disallowedTools') + 1], 'Agent,Bash,Edit,Write')
            self.assertEqual(command[command.index('--effort') + 1], 'high')
            self.assertIn('Work directly', (cwd / 'CLAUDE.md').read_text())
            stdout.write_text(''.join(json.dumps(e) + '\n' for e in events))
            stderr.write_text('')
            return {'exit_code': 0, 'timed_out': False, 'error': None, 'duration_seconds': 2.5}
        mutated, diff, line = bench.build_case(case, source)
        with tempfile.TemporaryDirectory() as temporary, patch.object(bench.fixer, 'execute', side_effect=fake_execute):
            record = bench.run_case('sonnet-high', case, source, b'tests', diff, line, b'Work directly.',
                                    Path(temporary) / 'run', 10)
        self.assertEqual(line, 196)
        self.assertEqual(record['status'], 'caught')
        self.assertEqual(record['total_cost_usd'], 0.25)
        self.assertEqual(record['usage'], [{'input_tokens': 3}])

    def test_summary_totals(self):
        def run(arm, case, kind, status, cost):
            return {'arm': arm, 'case': case, 'kind': kind, 'status': status, 'seconds': 1.0, 'total_cost_usd': cost}
        runs = [run('a', 'd1', 'defect', 'caught', 1.0), run('a', 'd2', 'defect', 'unparsed', 1.0),
                run('a', 'c1', 'clean', 'correct', None)]
        totals = bench.summarize(runs, ['a'])['arms']['a']
        self.assertEqual((totals['defects_caught'], totals['defects_total']), (1, 2))
        self.assertEqual((totals['clean_correct'], totals['clean_total'], totals['unparsed']), (1, 1, 1))
        self.assertEqual((totals['total_cost_usd'], totals['cost_per_caught_defect_usd']), (2.0, 2.0))


if __name__ == '__main__':
    unittest.main()

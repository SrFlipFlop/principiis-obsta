"""Public operator boundaries; controls here are never live qualification."""
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
from support import temporary_directory
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OperatorEvaluationCLI(unittest.TestCase):
    def setUp(self):
        self.temporary = temporary_directory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.runs = self.base / 'runs'
        self.run = self.runs / 'portal-test'
        auth = self.base / 'auth.json'
        auth.write_text('engineering fixture; no account access')
        runtime = self.base / 'runtime.json'
        runtime.write_text(json.dumps({
            'version': '1', 'docker': '/usr/bin/true', 'image': 'sha256:' + 'a' * 64,
            'auth_file': str(auth), 'clean_runtime_review': 'engineering fixture only',
        }))
        self.cli('init', '--application', 'document-portal', '--runtime-config', str(runtime))

    def cli(self, command, *arguments, success=True):
        result = subprocess.run([
            sys.executable, '-m', 'principiis', command, '--run', 'portal-test',
            '--runs-root', str(self.runs), *arguments,
        ], cwd=ROOT, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def test_unbound_evaluation_refuses_before_assessment_allocation(self):
        rejected = self.cli('evaluate', '--step', '1', success=False)
        self.assertIn('unbound', rejected.stderr)
        self.assertFalse((self.run / 'assessments').exists())
        self.assertFalse((self.run / 'development').exists())

    def test_saved_reports_keep_primary_and_rerun_rows_with_separate_resources(self):
        from principiis import resource
        from principiis import reporting
        from principiis.run_store import RunStore
        report = json.loads(self.cli('status', '--format', 'json').stdout)
        assessments = []
        attempts = []
        for number, role, outcome, duration in ((1, 'primary', 'candidate_failure', 2),
                                                 (2, 'rerun', 'evaluator_error', 3)):
            # Reports render the status dictionary; these assessments need no files on disk.
            path = self.run / 'development/evaluations/step-01' / str(number) / 'result.json'
            assessment = {
                'run_id': 'engineering-control', 'session_id': f'assessment-{number}',
                'checkpoint': 'step-01', 'attempt': number, 'role': role,
                'outcome': outcome, 'functional': 'pass' if number == 1 else 'unknown',
                'security': 'fail' if number == 1 else 'unknown',
                'stage': 'independent_evaluation', 'snapshot': '/retained/snapshot',
                'snapshot_manifest_sha256': 'b' * 64,
                'provenance': {'version': 'engineering-v1', 'manifest_sha256': 'c' * 64},
                'evaluation': {'elapsed_seconds': duration, 'started_at': 100 + number * 10,
                               'finished_at': 100 + number * 10 + duration,
                               'memory': {'scope': 'engineering evaluator subprocess',
                                          'peak_sampled_rss_bytes': 123}, 'tokens': None},
            }
            assessments.append(dict(assessment, artifact=str(path)))
            attempts.append({'run_id': assessment['run_id'], 'session_id': assessment['session_id'],
                             'checkpoint': 'step-01', 'attempt': number, 'outcome': outcome,
                             'artifact': str(path), 'stages': {'development': {}, 'evaluation': assessment['evaluation']}})
        report.update(assessments=assessments, assessment_binding={'version': 'engineering-v1'},
                      resources=resource.summarize(attempts))
        output = RunStore(self.run).save_reports(reporting.files(report))
        rows = list(csv.DictReader(io.StringIO((output / 'development.csv').read_text())))
        self.assertEqual([row['stage'] for row in rows], ['evaluation', 'evaluation'])
        self.assertEqual([row['role'] for row in rows], ['primary', 'rerun'])
        self.assertEqual([row['outcome'] for row in rows], ['candidate_failure', 'evaluator_error'])
        self.assertEqual(sum(float(row['evaluation_seconds']) for row in rows), 5)
        self.assertEqual([row['total_tokens'] for row in rows], ['unknown', 'unknown'])
        self.assertEqual([row['evaluator_version'] for row in rows], ['engineering-v1', 'engineering-v1'])
        readable = (output / 'development.md').read_text()
        self.assertIn('candidate_failure', readable)
        self.assertIn('evaluator_error', readable)
        self.assertIn('primary', readable)
        self.assertEqual(json.loads((output / 'development.json').read_text())['assessments'], assessments)

    def test_operator_assesses_without_development_and_rerun_preserves_primary(self):
        import test_assessment_cli
        fixture = test_assessment_cli.QualifiedAssessmentCLI()
        fixture.setUp()
        self.addCleanup(fixture.temporary.cleanup)
        docker = fixture.base / 'unavailable-image-docker'
        docker.write_text('#!' + sys.executable + '\nimport sys\nsys.exit(0 if "rm" in sys.argv else 1)\n')
        docker.chmod(0o755)
        fixture.make_run({'image': fixture.image, 'docker': str(docker)})
        fixture.generate_checkpoint()
        before = {path: path.read_bytes() for path in (fixture.root / 'development/steps/step-01').rglob('*') if path.is_file()}
        operator = fixture.operator
        fixture.bind()
        first = operator('evaluate', '--step', '1')
        primary = first['checkpoints'][0]['primary_assessment']
        self.assertEqual(primary['outcome'], 'evaluator_error')
        primary_path = Path(primary['artifact'])
        original_primary = primary_path.read_bytes()
        rejected = operator('evaluate', '--step', '1', success=False)
        self.assertIn('--rerun', rejected.stderr)
        rerun = operator('evaluate', '--step', '1', '--rerun')
        self.assertEqual(len(rerun['checkpoints'][0]['assessments']), 2)
        self.assertEqual(rerun['checkpoints'][0]['primary_assessment'], primary)
        self.assertEqual(primary_path.read_bytes(), original_primary)
        report = operator('report')
        self.assertEqual(report['resources']['totals']['development']['attempts_present'], 1)
        self.assertEqual(report['resources']['totals']['evaluation']['attempts_present'], 2)
        self.assertIsNone(report['resources']['totals']['evaluation']['tokens'])
        with (fixture.root / 'reports/development.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([row['stage'] for row in rows], ['development', 'evaluation', 'evaluation'])
        self.assertEqual([row['role'] for row in rows[1:]], ['primary', 'rerun'])
        self.assertTrue(all(row['evaluator_version'] == 'engineering-1' for row in rows[1:]))
        for path, contents in before.items():
            self.assertEqual(path.read_bytes(), contents)
        # A controller can die after its durable allocation and before a result
        # write. The allocation still supplies identity/provenance, never scores.
        Path(rerun['assessments'][1]['artifact']).unlink()
        interrupted = operator('report')
        self.assertEqual(interrupted['resources']['totals']['evaluation']['attempts_present'], 2)
        self.assertIsNone(interrupted['resources']['totals']['evaluation']['duration_seconds'])
        with (fixture.root / 'reports/development.csv').open() as stream:
            interrupted_rows = list(csv.DictReader(stream))
        self.assertEqual(interrupted_rows[2]['role'], 'rerun')
        self.assertEqual(interrupted_rows[2]['evaluator_version'], 'engineering-1')
        self.assertEqual(interrupted_rows[2]['snapshot_manifest_sha256'], primary['snapshot_manifest_sha256'])
        self.assertEqual(interrupted_rows[2]['source'], primary['snapshot'])
        self.assertEqual(interrupted_rows[2]['evaluation_seconds'], 'unknown')

    def test_unresolved_evaluator_cleanup_blocks_reruns_until_explicit_cleanup(self):
        import test_assessment_cli
        fixture = test_assessment_cli.QualifiedAssessmentCLI()
        fixture.setUp()
        self.addCleanup(fixture.temporary.cleanup)
        # Fail image inspection, then fail removal until the operator fixes the
        # external Docker boundary. The frozen runtime configuration never changes.
        marker = fixture.base / 'cleanup-allowed'
        docker = fixture.base / 'docker-control'
        docker.write_text('#!' + sys.executable + '\nimport pathlib,sys\n'
                          f'allowed=pathlib.Path({str(marker)!r}).exists()\n'
                          'if "rm" in sys.argv and allowed:\n'
                          ' print("Error response from daemon: No such container: " + sys.argv[-1], file=sys.stderr)\n'
                          'sys.exit(1)\n')
        docker.chmod(0o755)
        fixture.make_run({'image': fixture.image, 'docker': str(docker)})
        fixture.generate_checkpoint()
        fixture.bind()

        def operator(command, *arguments):
            return fixture.operator(command, *arguments, success=None)

        first = operator('evaluate', '--step', '1')
        self.assertEqual(first.returncode, 0, first.stderr)
        report = json.loads(first.stdout)
        self.assertEqual(report['next_action']['action'], 'cleanup-evaluation')
        primary = Path(report['assessments'][0]['artifact'])
        original = primary.read_bytes()
        blocked = operator('evaluate', '--step', '1', '--rerun')
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn('cleanup', blocked.stderr)
        self.assertEqual(len(fixture.operator('status')['assessments']), 1)
        marker.touch()
        cleaned = operator('cleanup-evaluation', '--step', '1')
        self.assertEqual(cleaned.returncode, 0, cleaned.stderr)
        self.assertEqual(json.loads(cleaned.stdout)['evaluation_cleanup_required'], [])
        self.assertEqual(primary.read_bytes(), original)
        rerun = operator('evaluate', '--step', '1', '--rerun')
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        self.assertEqual(len(json.loads(rerun.stdout)['assessments']), 2)
        self.assertEqual(primary.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()

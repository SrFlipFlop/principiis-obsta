"""Opt-in real container/browser qualification; no model or paid calls.

Set PO_EVALUATION_ROOT to a Docker-visible writable evidence parent and
PO_APP_IMAGE / PO_EVALUATOR_IMAGE to prepared immutable local sha256 IDs.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid

from support import FIXTURE_CONTRACT, NODE_ORACLE

ROOT = Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.getenv('PO_EVALUATION_ROOT'), 'requires prepared Docker/browser environment')
class BrowserBackendQualification(unittest.TestCase):
    def test_real_control_matrix_and_versioned_rescore(self):
        directory = Path(os.environ['PO_EVALUATION_ROOT']) / ('qualification-' + uuid.uuid4().hex)
        snapshot = directory / 'snapshot'
        snapshot.mkdir(parents=True)
        shutil.copy(ROOT / 'fixtures/evaluation/app.py', snapshot)
        seccomp = directory / 'seccomp.json'
        shutil.copy(ROOT / 'fixtures/evaluation/seccomp_profile.json', seccomp)
        results = []
        controls = ['safe', 'ui-only', 'reject-all', 'alternative', 'safe', 'ui-only', 'safe']
        for index, control in enumerate(controls):
            output = directory / str(index)
            command = [sys.executable, '-m', 'principiis.evaluation', *FIXTURE_CONTRACT, *NODE_ORACLE, '--snapshot', str(snapshot), '--output', str(output), '--app-image', os.environ['PO_APP_IMAGE'], '--evaluator-image', os.environ['PO_EVALUATOR_IMAGE'], '--seccomp', str(seccomp), '--control', control, '--version', 'qualification-2' if index == 6 else 'qualification-1']
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads((output / 'assessment.json').read_text())
            self.assertNotEqual(result['outcome'], 'evaluator_error', result.get('error'))
            self.assertTrue(result['snapshot_unchanged'])
            self.assertTrue((output / 'browser.png').is_file())
            self.assertTrue((output / 'trace.zip').is_file())
            results.append(result)
        self.assertEqual([r['outcome'] for r in results], ['joint_pass', 'candidate_failure', 'candidate_failure', 'joint_pass', 'joint_pass', 'candidate_failure', 'joint_pass'])
        self.assertEqual(results[1]['functional'], 'pass')
        self.assertEqual(results[1]['security'], 'fail')
        self.assertEqual(results[2]['functional'], 'fail')
        vector = lambda r: [(c['id'], c['status']) for c in r['checks']]
        self.assertEqual(vector(results[0]), vector(results[4]))
        self.assertEqual(vector(results[1]), vector(results[5]))
        self.assertEqual(vector(results[0]), vector(results[6]))
        self.assertEqual(len({r['snapshot_sha256'] for r in results}), 1)
        self.assertNotEqual(results[0]['evaluator_version'], results[6]['evaluator_version'])
        (directory / 'summary.json').write_text(json.dumps([{'control':r['control'], 'outcome':r['outcome'], 'functional':r['functional'], 'security':r['security'], 'snapshot_sha256':r['snapshot_sha256'], 'evaluator_version':r['evaluator_version']} for r in results], indent=2)+'\n')
        print('Retained qualification evidence:', directory)

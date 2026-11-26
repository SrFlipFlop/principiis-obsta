"""Opt-in browser/backend engineering control; never a generated portal result."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
import uuid

from principiis.snapshot import preserve, validate
from support import FIXTURE_CONTRACT, NODE_ORACLE

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.getenv('PO_EVALUATION_ROOT'), 'requires prepared Docker/browser environment')
class RuntimeBoundEvaluation(unittest.TestCase):
    def test_browser_backend_checks_run_with_retained_interpreter_link(self):
        base = Path(os.environ['PO_EVALUATION_ROOT']) / ('runtime-control-' + uuid.uuid4().hex)
        source = base / 'source'
        source.mkdir(parents=True)
        shutil.copy(ROOT / 'fixtures/evaluation/app.py', source / 'app.py')
        application = source / 'app.py'
        application.write_text('from pathlib import Path\n'
                               'assert Path.cwd() == Path("/workspace")\n'
                               'Path("runtime-created.txt").write_text("disposable application data")\n'
                               + application.read_text())
        (source / 'json.py').write_text('raise RuntimeError("candidate module must not enter the containment probe")\n')
        interpreter = source / '.venv/bin/python'
        interpreter.parent.mkdir(parents=True)
        interpreter.symlink_to('/usr/local/bin/python3.12')
        image = os.environ['PO_APP_IMAGE']
        snapshot = base / 'snapshot'
        preserve(source, snapshot, runtime_binding={
            'image': image, 'symlink_targets': ['/usr/local/bin/python3.12'],
        })
        original_manifest = snapshot.with_suffix('.json').read_bytes()
        output = base / 'assessment'
        seccomp = base / 'seccomp.json'
        shutil.copy(ROOT / 'fixtures/evaluation/seccomp_profile.json', seccomp)
        command = [sys.executable, '-m', 'principiis.evaluation', *FIXTURE_CONTRACT, *NODE_ORACLE, '--snapshot', str(snapshot),
                   '--output', str(output), '--app-image', image,
                   '--evaluator-image', os.environ['PO_EVALUATOR_IMAGE'],
                   '--docker', os.environ.get('PO_EVALUATION_DOCKER', 'docker'),
                   '--seccomp', str(seccomp),
                   '--app-command', json.dumps(['.venv/bin/python', '-I', 'app.py', 'safe'])]
        summary = {'scope': 'model-free engineering browser/backend control, not portal qualification',
                   'command': command, 'outcome': 'error'}
        try:
            process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
            (base / 'controller.stdout').write_text(process.stdout)
            (base / 'controller.stderr').write_text(process.stderr)
            self.assertEqual(process.returncode, 0, process.stderr)
            assessment = json.loads((output / 'assessment.json').read_text())
            self.assertEqual(assessment['outcome'], 'joint_pass', assessment.get('error'))
            self.assertTrue(assessment['snapshot_unchanged'])
            self.assertFalse(assessment.get('cleanup_errors'))
            self.assertTrue((output / 'browser.png').is_file())
            self.assertTrue((output / 'trace.zip').is_file())
            self.assertFalse((snapshot / 'runtime-created.txt').exists())
            validate(snapshot, runtime_image=image)
            self.assertEqual(snapshot.with_suffix('.json').read_bytes(), original_manifest)
            self.assertEqual(os.readlink(snapshot / '.venv/bin/python'), '/usr/local/bin/python3.12')
            summary['outcome'] = 'pass'
        except BaseException as error:
            summary['error'] = str(error)
            raise
        finally:
            (base / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
            print('Retained runtime control evidence:', base)

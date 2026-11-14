import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SequenceCLI(unittest.TestCase):
    def test_failing_checkpoint_advances_with_notes_and_cumulative_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'one.txt').write_text('Build first')
            (base / 'two.txt').write_text('Add second FUTURE_SENTINEL')
            (base / 'check.py').write_text("import json,pathlib; print(json.dumps({'functional': 'pass' if pathlib.Path('next').exists() else 'fail', 'security':'pass'}))")
            (base / 'executor.py').write_text("""import pathlib,sys,os
request = sys.stdin.read()
p = pathlib.Path('.')
if not (p / 'notes').exists():
    assert list(p.iterdir()) == []
    assert request == 'Build first'
    (p / 'notes').write_text('retained note')
    (p / 'pid').write_text(str(os.getpid()))
else:
    assert (p / 'notes').read_text() == 'retained note'
    assert request == 'Build first\\n\\nAdd second FUTURE_SENTINEL'
    assert (p / 'pid').read_text() != str(os.getpid())
    (p / 'next').write_text('done')
if not (p / 'next').exists():
    assert 'FUTURE_SENTINEL' not in request
""")
            manifest = {'id':'sample','version':'1','condition':{'id':'ordinary','version':'1'},'steps':[
                {'id':'one','version':'1','sequence_version':'1','request':'one.txt','check':[sys.executable,'check.py']},
                {'id':'two','version':'1','sequence_version':'1','request':'two.txt','check':[sys.executable,'check.py']}]}
            (base / 'sequence.json').write_text(json.dumps(manifest))
            for name in ('run-a', 'run-b'):
                completed = subprocess.run([sys.executable,'-m','principiis','sequence','--sequence',str(base/'sequence.json'),'--executor',json.dumps([sys.executable,str(base/'executor.py')]),'--output',str(base/name)],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(completed.returncode,0,completed.stderr)
                first = json.loads((base/name/'steps/one/result.json').read_text())
                second = json.loads((base/name/'steps/two/result.json').read_text())
                self.assertEqual((first['outcome'],second['outcome']),('candidate_failure','joint_pass'))
                self.assertEqual(first['run_id'],second['run_id'])
                self.assertNotEqual(first['session_id'],second['session_id'])
                self.assertFalse((base/name/'steps/one/snapshot/next').exists())

    def test_invalid_sequence_is_rejected_before_any_artifacts_or_executor(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base/'request.txt').write_text('visible')
            valid = {'id':'first','version':'1','sequence_version':'1','request':'request.txt','check':['unused-check']}
            cases = [
                [dict(valid, id=''), valid],
                [valid, valid],
                [dict(valid, sequence_version='2')],
                [dict(valid, id='../escape')],
            ]
            for index, steps in enumerate(cases):
                task = base/'sequence.json'
                task.write_text(json.dumps({'id':'sample','version':'1','condition':{'id':'ordinary','version':'1'},'steps':steps}))
                output = base/str(index)
                completed = subprocess.run([sys.executable,'-m','principiis','sequence','--sequence',str(task),'--executor','["unused-executor"]','--output',str(output)],cwd=ROOT,capture_output=True)
                self.assertNotEqual(completed.returncode,0)
                self.assertFalse(output.exists())
            task.write_text(json.dumps({'id':'sample','version':'1','steps':[valid]}))
            output = base/'missing-condition'
            completed = subprocess.run([sys.executable,'-m','principiis','sequence','--sequence',str(task),'--executor','["unused-executor"]','--output',str(output)],cwd=ROOT,capture_output=True)
            self.assertNotEqual(completed.returncode,0)
            self.assertFalse(output.exists())

    def test_incomplete_step_retains_partial_files_and_does_not_reveal_next_request(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base/'one.txt').write_text('first')
            (base/'two.txt').write_text('future')
            (base/'executor.py').write_text("import pathlib,sys; assert sys.stdin.read() == 'first'; pathlib.Path('partial').write_text('keep'); sys.exit(7)")
            steps = [{'id':key,'version':'1','sequence_version':'1','request':key+'.txt','check':['unused-check']} for key in ('one','two')]
            (base/'sequence.json').write_text(json.dumps({'id':'sample','version':'1','condition':{'id':'ordinary','version':'1'},'steps':steps}))
            output = base/'run'
            completed = subprocess.run([sys.executable,'-m','principiis','sequence','--sequence',str(base/'sequence.json'),'--executor',json.dumps([sys.executable,str(base/'executor.py')]),'--output',str(output)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            self.assertEqual((output/'steps/one/workspace/partial').read_text(),'keep')
            self.assertFalse((output/'steps/one/snapshot').exists())
            self.assertFalse((output/'steps/two').exists())
            summary = json.loads((output/'sequence.json').read_text())
            self.assertEqual(summary['status'],'incomplete')
            self.assertEqual(summary['checkpoints'],[{'id':'one','outcome':'incomplete','artifact':'steps/one'}])

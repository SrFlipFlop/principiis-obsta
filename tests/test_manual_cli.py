import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ManualCLI(unittest.TestCase):
    def test_develop_then_explicit_versioned_evaluation_and_next(self):
        with tempfile.TemporaryDirectory() as d:
            b=Path(d)
            (b/'one.txt').write_text('first')
            (b/'two.txt').write_text('second')
            (b/'agent.py').write_text("import pathlib,sys; pathlib.Path('notes').write_text(sys.stdin.read()); print('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":3,\"output_tokens\":2}}')")
            (b/'check.py').write_text("print('{\"functional\":\"pass\",\"security\":\"fail\"}')")
            m={'id':'sample','version':'1','condition':{'id':'ordinary','version':'1'},'steps':[{'id':s,'version':'1','sequence_version':'1','request':s+'.txt','check':[sys.executable,'check.py']} for s in ('one','two')]}
            (b/'sequence.json').write_text(json.dumps(m))
            (b/'suite.json').write_text(json.dumps({'id':'suite','version':'1','applications':[{'id':'sample','sequence':'sequence.json'}]}))
            def cli(*args):
                if args[0] == 'evaluate':
                    version = args[args.index('--evaluator-version') + 1]
                    manifest = b/'evaluator.json'
                    manifest.write_text(json.dumps({'version':version,'complete':True,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in b.glob('*.py')}}))
                    args = (*args, '--evaluator-manifest', str(manifest))
                p=subprocess.run([sys.executable,'-m','principiis.manual',*args],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)
            prepare=subprocess.run([sys.executable,'-m','principiis.suite','prepare','--suite',str(b/'suite.json'),'--output',str(b/'suite-run')],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(prepare.returncode,0,prepare.stderr)
            (b/'suite-run/applications').mkdir()
            # Standard suite location can be populated one manual checkpoint at a time.
            (b/'suite-run/applications/sample').symlink_to(b/'run',target_is_directory=True)
            cli('develop','--sequence',str(b/'sequence.json'),'--output',str(b/'run'),'--step','one','--executor',json.dumps([sys.executable,str(b/'agent.py')]))
            result=b/'run/steps/one/result.json'
            original=result.read_bytes()
            self.assertEqual(json.loads(original)['outcome'],'pending_evaluation')
            self.assertFalse((b/'run/steps/two').exists())
            for _ in range(2):
                cli('evaluate','--output',str(b/'run'),'--step','one','--evaluator-version','1')
            self.assertEqual(result.read_bytes(),original)
            first=json.loads((b/'run/evaluations/one/1/result.json').read_text())
            second=json.loads((b/'run/evaluations/one/2/result.json').read_text())
            self.assertEqual((first['role'],second['role']),('primary','rerun'))
            self.assertEqual(first['outcome'],'candidate_failure')
            suite=subprocess.run([sys.executable,'-m','principiis.suite','report','--output',str(b/'suite-run')],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(suite.returncode,0,suite.stderr)
            suite_report=json.loads(suite.stdout)
            self.assertEqual(suite_report['outcomes'],{'candidate_failure':1})
            self.assertEqual(suite_report['attempts'][0]['developer_outcome'],'pending_evaluation')
            self.assertTrue(suite_report['attempts'][0]['primary_assessment_ref'].endswith('/evaluations/one/1/result.json'))
            self.assertEqual(len(suite_report['evaluations']),1)
            self.assertEqual(suite_report['resources']['totals']['evaluation']['attempts_present'],1)
            markdown=subprocess.run([sys.executable,'-m','principiis.suite','report','--output',str(b/'suite-run'),'--format','markdown'],cwd=ROOT,capture_output=True,text=True)
            self.assertIn(first['provenance']['version'], markdown.stdout)
            self.assertIn('/evaluations/one/1/result.json', markdown.stdout)
            self.assertIn('pending_evaluation', markdown.stdout)
            resources=subprocess.run([sys.executable,'-m','principiis.resource',str(b/'run')],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(resources.returncode,0,resources.stderr)
            report=json.loads(resources.stdout)
            self.assertEqual(report['totals']['development']['attempts_present'],1)
            self.assertEqual(report['totals']['evaluation']['attempts_present'],2)
            self.assertEqual(report['totals']['development']['tokens']['total_tokens'],5)
            cli('develop','--sequence',str(b/'sequence.json'),'--output',str(b/'run'),'--step','two','--executor',json.dumps([sys.executable,str(b/'agent.py')]))
            self.assertEqual((b/'run/steps/two/snapshot/notes').read_text(),'first\n\nsecond')
            (b/'check.py').write_text('raise SystemExit(1)')
            changed=subprocess.run([sys.executable,'-m','principiis.manual','develop','--sequence',str(b/'sequence.json'),'--output',str(b/'run'),'--step','two','--executor',json.dumps([sys.executable,str(b/'agent.py')])],cwd=ROOT,capture_output=True,text=True)
            self.assertNotEqual(changed.returncode,0)
            self.assertIn('configuration changed',changed.stderr)

    def test_interrupted_attempt_retains_usage_and_explicit_retries_stop_at_three(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            b=Path(d)
            (b/'request').write_text('visible')
            (b/'agent.py').write_text("import pathlib,time; pathlib.Path('partial').write_text('keep'); print('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":7,\"output_tokens\":1}}',flush=True); time.sleep(60)")
            m={'id':'sample','version':'1','condition':{'id':'ordinary','version':'1'},'steps':[{'id':'one','version':'1','sequence_version':'1','request':'request','check':['never-evaluate']}]}
            (b/'sequence').write_text(json.dumps(m))
            cmd=[sys.executable,'-m','principiis.manual','develop','--sequence',str(b/'sequence'),'--output',str(b/'run'),'--step','one','--executor',json.dumps([sys.executable,str(b/'agent.py')])]
            p=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            partial=b/'run/steps/one/workspace/partial'
            deadline=time.monotonic()+5
            while not partial.exists() and time.monotonic()<deadline:
                time.sleep(.01)
            self.assertTrue(partial.exists())
            p.terminate(); p.communicate(timeout=5)
            first=json.loads((b/'run/steps/one/result.json').read_text())
            self.assertFalse(first['completed'])
            self.assertIsNone(first['execution']['exit_status'])
            self.assertGreater(first['execution']['elapsed_seconds'],0)
            self.assertIn('turn.completed',(b/'run/steps/one/executor.stdout').read_text())
            self.assertNotEqual(subprocess.run(cmd,cwd=ROOT,capture_output=True).returncode,0)
            (b/'agent.py').write_text("import pathlib,sys; assert not pathlib.Path('partial').exists(); pathlib.Path('failed').write_text('keep'); sys.exit(1)")
            for _ in range(3):
                p=subprocess.run(cmd+['--retry'],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)
            p=subprocess.run(cmd+['--retry'],cwd=ROOT,capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn('three additional retries exhausted',p.stderr)
            self.assertEqual(len(json.loads((b/'run/manual.json').read_text())['attempts']),4)

    def test_failed_primary_stays_primary_when_new_version_rerun_passes(self):
        with tempfile.TemporaryDirectory() as d:
            b=Path(d)
            (b/'request').write_text('visible')
            (b/'policy.py').write_text('raise SystemExit(1)')
            (b/'check.py').write_text('import policy')
            (b/'sequence').write_text(json.dumps({'id':'sample','version':'1','condition':{'id':'ordinary','version':'1'},'steps':[{'id':'one','version':'1','sequence_version':'1','request':'request','check':[sys.executable,'check.py']}]}))
            def cli(*args):
                if args[0] == 'evaluate':
                    version = args[args.index('--evaluator-version') + 1]
                    manifest = b/'evaluator.json'
                    manifest.write_text(json.dumps({'version':version,'complete':True,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in b.glob('*.py')}}))
                    args = (*args, '--evaluator-manifest', str(manifest))
                return subprocess.run([sys.executable,'-m','principiis.manual',*args],cwd=ROOT,capture_output=True,text=True)
            p=cli('develop','--sequence',str(b/'sequence'),'--output',str(b/'run'),'--step','one','--executor',json.dumps([sys.executable,'-c','pass']))
            self.assertEqual(p.returncode,0,p.stderr)
            evaluation=['evaluate','--output',str(b/'run'),'--step','one','--evaluator-version']
            self.assertEqual(cli(*evaluation,'1').returncode,0)
            primary=b/'run/evaluations/one/1/result.json'
            original=primary.read_bytes()
            self.assertEqual(json.loads(original)['outcome'],'evaluator_error')
            # Persisted crash fixture: allocation ledger committed, directory not created yet.
            allocated=json.loads(original)
            shutil.rmtree(primary.parent)
            self.assertEqual(cli(*evaluation,'1').returncode,0)
            recovered=json.loads(primary.read_text())
            self.assertEqual(recovered['session_id'],allocated['session_id'])
            self.assertEqual(recovered['provenance'],allocated['provenance'])
            self.assertEqual((recovered['role'],recovered['outcome']),('primary','evaluator_error'))
            self.assertIn('interrupted',recovered['error'])
            original=primary.read_bytes()
            (b/'policy.py').write_text("print('{\"functional\":\"pass\",\"security\":\"pass\"}')")
            p=cli(*evaluation,'1')
            self.assertNotEqual(p.returncode,0)
            self.assertIn('new evaluator version',p.stderr)
            self.assertEqual(cli(*evaluation,'2').returncode,0)
            self.assertEqual(primary.read_bytes(),original)
            rerun=json.loads((b/'run/evaluations/one/3/result.json').read_text())
            self.assertEqual((rerun['role'],rerun['outcome']),('rerun','joint_pass'))

    def test_legacy_orphan_is_retained_as_unknown_primary(self):
        with tempfile.TemporaryDirectory() as d:
            b=Path(d)
            (b/'request').write_text('visible')
            (b/'check.py').write_text("print('{\"functional\":\"pass\",\"security\":\"pass\"}')")
            (b/'sequence').write_text(json.dumps({'id':'sample','version':'1','condition':{'id':'ordinary','version':'1'},'steps':[{'id':'one','version':'1','sequence_version':'1','request':'request','check':[sys.executable,'check.py']}]}))
            def cli(*args):
                return subprocess.run([sys.executable,'-m','principiis.manual',*args],cwd=ROOT,capture_output=True,text=True)
            p=cli('develop','--sequence',str(b/'sequence'),'--output',str(b/'run'),'--step','one','--executor',json.dumps([sys.executable,'-c','pass']))
            self.assertEqual(p.returncode,0,p.stderr)
            orphan=b/'run/evaluations/one/1'
            orphan.mkdir(parents=True)
            (orphan/'evidence').write_text('retained')
            manifest=b/'manifest.json'
            manifest.write_text(json.dumps({'version':'1','complete':True,'files':{'check.py':hashlib.sha256((b/'check.py').read_bytes()).hexdigest()}}))
            p=cli('evaluate','--output',str(b/'run'),'--step','one','--evaluator-version','1','--evaluator-manifest',str(manifest))
            self.assertEqual(p.returncode,0,p.stderr)
            primary=json.loads((orphan/'result.json').read_text())
            self.assertEqual((primary['role'],primary['outcome']),('primary','evaluator_error'))
            self.assertIsNone(primary['provenance']['version'])
            self.assertIn('unknown',primary['error'])
            self.assertEqual((orphan/'evidence').read_text(),'retained')
            resources=subprocess.run([sys.executable,'-m','principiis.resource',str(b/'run')],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(resources.returncode,0,resources.stderr)
            self.assertEqual(len(json.loads(resources.stdout)['attempts']),3)
            (b/'suite.json').write_text(json.dumps({'id':'suite','version':'1','applications':[{'id':'sample','sequence':'sequence'}]}))
            prepared=subprocess.run([sys.executable,'-m','principiis.suite','prepare','--suite',str(b/'suite.json'),'--output',str(b/'suite-run')],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(prepared.returncode,0,prepared.stderr)
            (b/'suite-run/applications').mkdir()
            (b/'suite-run/applications/sample').symlink_to(b/'run',target_is_directory=True)
            report=subprocess.run([sys.executable,'-m','principiis.suite','report','--output',str(b/'suite-run'),'--format','markdown'],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(report.returncode,0,report.stderr)
            self.assertIn('/evaluations/one/1/result.json',report.stdout)
            self.assertIn('evaluator_error',report.stdout)
            self.assertIn('pending_evaluation',report.stdout)
            self.assertEqual(json.loads((b/'run/evaluations/one/2/result.json').read_text())['role'],'rerun')

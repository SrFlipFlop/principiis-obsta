import json
from pathlib import Path
import subprocess
import sys
from support import temporary_directory
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ResumeCLI(unittest.TestCase):
    def test_retry_preserves_failed_checkpoint_and_incomplete_attempt(self):
        with temporary_directory() as directory:
            base = Path(directory)
            for name in ('one', 'two'):
                (base / (name + '.txt')).write_text(name)
            (base / 'check.py').write_text("print('{\"functional\":\"fail\",\"security\":\"pass\"}')")
            (base / 'executor.py').write_text('''import pathlib,sys
p=pathlib.Path('.')
r=sys.stdin.read()
if r == 'one':
    assert list(p.iterdir()) == []
    (p/'retained').write_text('first')
else:
    assert (p/'retained').read_text() == 'first'
    assert not (p/'partial').exists()
    (p/'partial').write_text('incomplete')
    if not pathlib.Path(__file__).with_name('retry-enabled').exists(): sys.exit(7)
''')
            manifest = {'id':'sample','version':'1','condition':{'id':'ordinary','version':'1'},'steps':[
                {'id':name,'version':'1','sequence_version':'1','request':name+'.txt','check':[sys.executable,'check.py']} for name in ('one','two')]}
            source = base/'sequence.json'
            source.write_text(json.dumps(manifest))
            output=base/'run'
            argv=[sys.executable,'-m','principiis','sequence','--sequence',str(source),'--executor',json.dumps([sys.executable,str(base/'executor.py')]),'--output',str(output)]
            def invoke(*options):
                return subprocess.run(argv+list(options),cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(invoke().returncode,0)
            old={str(p.relative_to(output)):p.read_bytes() for p in (output/'steps').rglob('*') if p.is_file()}
            self.assertNotEqual(invoke('--resume').returncode,0)
            (base/'retry-enabled').touch()
            retried=invoke('--resume','--retry-incomplete')
            self.assertEqual(retried.returncode,0,retried.stderr)
            for name, content in old.items(): self.assertEqual((output/name).read_bytes(),content)
            summary=json.loads((output/'sequence.json').read_text())
            self.assertEqual(summary['status'],'completed')
            attempt=json.loads((output/summary['checkpoints'][-1]['artifact']/'result.json').read_text())
            first=json.loads((output/'steps/two/result.json').read_text())
            self.assertEqual(attempt['attempt'],2)
            self.assertNotEqual(attempt['session_id'],first['session_id'])
            self.assertEqual(summary['checkpoints'][0]['outcome'],'candidate_failure')
            self.assertEqual(invoke('--resume').returncode,0)
            (base/'one.txt').write_text('changed without version bump')
            self.assertNotEqual(invoke('--resume').returncode,0)

    def test_interrupt_cleanup_resume_and_configuration_rejection(self):
        import os
        import signal
        import time
        with temporary_directory() as directory:
            base=Path(directory)
            (base/'one.txt').write_text('one')
            (base/'two.txt').write_text('two')
            (base/'check.py').write_text("print('{\"functional\":\"pass\",\"security\":\"pass\"}')")
            (base/'executor.py').write_text('''import pathlib,sys,time,os
p=pathlib.Path('.')
request=sys.stdin.read()
if request=='one': (p/'retained').write_text('checkpoint')
else:
    assert (p/'retained').read_text()=='checkpoint'
    assert not (p/'partial').exists()
    (p/'partial').write_text(str(os.getpid()))
    print('started',flush=True)
    if not pathlib.Path(__file__).with_name('proceed').exists(): time.sleep(60)
''')
            manifest={'id':'interrupt','version':'1','condition':{'id':'ordinary','version':'1'},'steps':[
                {'id':name,'version':'1','sequence_version':'1','request':name+'.txt','check':[sys.executable,'check.py']} for name in ('one','two')]}
            source=base/'sequence.json'
            source.write_text(json.dumps(manifest))
            output=base/'run'
            argv=[sys.executable,'-m','principiis','sequence','--sequence',str(source),'--executor',json.dumps([sys.executable,str(base/'executor.py')]),'--output',str(output)]
            process=subprocess.Popen(argv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    if (output/'steps/two/executor.stdout').exists() and 'started' in (output/'steps/two/executor.stdout').read_text(): break
                    time.sleep(.02)
                else: self.fail('executor never reached interrupt boundary')
                process.send_signal(signal.SIGTERM)
                process.communicate(timeout=5)
                first=(output/'steps/one/result.json').read_bytes()
                interrupted=(output/'steps/two/result.json').read_bytes()
                partial=(output/'steps/two/workspace/partial').read_bytes()
                result=json.loads(interrupted)
                self.assertEqual(result['outcome'],'incomplete')
                self.assertIn('interrupt',result['execution']['error'])
                self.assertGreater(result['execution']['elapsed_seconds'],0)
                child=int(partial)
                with self.assertRaises(ProcessLookupError): os.kill(child,0)
                (base/'proceed').touch()
                config_argv=argv.copy()
                config_argv[config_argv.index('--executor')+1]=json.dumps([sys.executable,str(base/'executor.py'),'different-config'])
                mismatch=subprocess.run(config_argv+['--resume','--retry-incomplete'],cwd=ROOT,capture_output=True)
                self.assertNotEqual(mismatch.returncode,0)
                resumed=subprocess.run(argv+['--resume','--retry-incomplete'],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(resumed.returncode,0,resumed.stderr)
                self.assertEqual((output/'steps/one/result.json').read_bytes(),first)
                self.assertEqual((output/'steps/two/result.json').read_bytes(),interrupted)
                self.assertEqual((output/'steps/two/workspace/partial').read_bytes(),partial)
                summary=json.loads((output/'sequence.json').read_text())
                self.assertEqual(summary['status'],'completed')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

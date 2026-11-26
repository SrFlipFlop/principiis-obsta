import json
from pathlib import Path
import subprocess
import sys
from support import temporary_directory
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CodexCLI(unittest.TestCase):
    def test_codex_sequence_uses_fresh_sessions_and_records_events_and_configuration(self):
        with temporary_directory() as directory:
            base = Path(directory)
            home = base / 'clean-codex'
            home.mkdir()
            fake = base / 'codex'
            fake.write_text('''#!/usr/bin/env python3
import json, pathlib, sys, os
if sys.argv[1:] == ['--version']:
    print('codex-cli fixture-1'); sys.exit()
args=sys.argv[1:]
assert args[:2] == ['--no-daemon','exec']
assert all(flag in args for flag in ['--ephemeral','--ignore-user-config','--ignore-rules','--json','--skip-git-repo-check'])
assert args[args.index('--model')+1] == 'fixture-model'
assert 'OPENAI_API_KEY' not in os.environ
assert not (pathlib.Path(os.environ['HOME'])/'.agents').exists()
request=sys.stdin.read()
p=pathlib.Path.cwd()
if not (p/'notes').exists():
    assert request == 'first request'
    assert 'FUTURE' not in request
    (p/'notes').write_text('keep')
else:
    assert request == 'first request\\n\\nFUTURE second'
print(json.dumps({'type':'item.completed','item':{'type':'command_execution','command':'ordinary command','exit_code':0}}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':3}}))
print('diagnostic',file=sys.stderr)
''')
            fake.chmod(0o755)
            (base/'one').write_text('first request')
            (base/'two').write_text('FUTURE second')
            (base/'check.py').write_text("print('{\"functional\":\"pass\",\"security\":\"pass\"}')")
            manifest = {'id':'sample','version':'1','condition':{'id':'ordinary','version':'1'},'steps':[
                {'id':key,'version':'1','sequence_version':'1','request':request,'check':[sys.executable,str(base/'check.py')]}
                for key,request in [('one','one'),('two','two')]]}
            (base/'sequence.json').write_text(json.dumps(manifest))
            config = {'executable':str(fake),'codex_home':str(home),'model':'fixture-model','reasoning_effort':'medium',
                      'sandbox':'workspace-write','approval_policy':'never','network_access':True,'web_search':'live',
                      'clean_runtime_review':'fixture runtime contains no researcher instructions, skills, hooks or external memory'}
            (base/'config.json').write_text(json.dumps(config))
            output = base/'output'
            completed = subprocess.run([sys.executable,'-m','principiis','sequence','--sequence',str(base/'sequence.json'),
                                       '--codex-config',str(base/'config.json'),'--output',str(output)],cwd=ROOT,text=True,capture_output=True,
                                      env=dict(__import__('os').environ,OPENAI_API_KEY='DO_NOT_INHERIT'))
            self.assertEqual(completed.returncode,0,completed.stderr)
            for step in ('one','two'):
                artifact=output/'steps'/step
                result=json.loads((artifact/'result.json').read_text())
                self.assertEqual(result['outcome'],'joint_pass')
                self.assertEqual(result['execution']['codex']['version'],'codex-cli fixture-1')
                self.assertEqual(result['execution']['codex']['access_mode'],'existing-chatgpt-subscription')
                self.assertIn('ordinary command',(artifact/'executor.stdout').read_text())
                self.assertEqual((artifact/'executor.stderr').read_text(),'diagnostic\n')
                self.assertNotIn('DO_NOT_INHERIT',(artifact/'result.json').read_text())

    def test_failed_codex_retains_partial_output_and_redacts_credentials(self):
        with temporary_directory() as directory:
            base=Path(directory)
            (base/'home').mkdir()
            fake=base/'codex'
            fake.write_text('''#!/usr/bin/env python3
import sys,pathlib
if sys.argv[1:] == ['--version']:
    print('fixture');sys.exit()
pathlib.Path('partial').write_text('retained')
print('{"type":"error","api_key":"secret-value"}')
print('Authorization: Bearer private-token',file=sys.stderr)
sys.exit(7)
''')
            fake.chmod(0o755)
            (base/'request').write_text('visible')
            (base/'task.json').write_text(json.dumps({'id':'task','version':'1','condition':{'id':'ordinary','version':'1'},'request':'request','check':['never-called']}))
            config={'executable':str(fake),'codex_home':str(base/'home'),'model':'fixture','reasoning_effort':'medium','sandbox':'workspace-write','approval_policy':'never','network_access':True,'web_search':'live','clean_runtime_review':'reviewed fixture'}
            (base/'config').write_text(json.dumps(config))
            output=base/'output'
            cmd=[sys.executable,'-m','principiis','run','--task',str(base/'task.json'),'--codex-config',str(base/'config'),'--output',str(output)]
            completed=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            result=json.loads((output/'result.json').read_text())
            self.assertEqual((result['outcome'],result['execution']['exit_status']),('incomplete',7))
            self.assertEqual((output/'workspace/partial').read_text(),'retained')
            self.assertNotIn('secret-value',(output/'executor.stdout').read_text())
            self.assertNotIn('private-token',(output/'executor.stderr').read_text())
            self.assertFalse((output/'snapshot').exists())
            for forbidden in ('skills','memories'):
                (base/'home'/forbidden).mkdir()
                config['codex_home']=str(base/'home')
                (base/'config').write_text(json.dumps(config))
                rejected=subprocess.run(cmd[:-1]+[str(base/('unsafe-'+forbidden))],cwd=ROOT,capture_output=True,text=True)
                self.assertNotEqual(rejected.returncode,0)
                self.assertFalse((base/('unsafe-'+forbidden)).exists())
                (base/'home'/forbidden).rmdir()

            for unsafe in (base, ROOT/'unsafe-agent-run'):
                rejected=subprocess.run(cmd[:-1]+[str(unsafe)],cwd=ROOT,capture_output=True,text=True)
                self.assertNotEqual(rejected.returncode,0)
                self.assertIn('development output must be separate',rejected.stderr)

    def test_default_settings_do_not_override_harness(self):
        with temporary_directory() as d:
            b=Path(d); (b/'home').mkdir()
            fake=b/'codex'
            fake.write_text('''#!/usr/bin/env python3
import sys,json
if sys.argv[1:] == ['--version']: print('fixture'); sys.exit()
assert '--model' not in sys.argv
assert not any('model_reasoning_effort' in a for a in sys.argv)
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':2}}))
'''); fake.chmod(0o755)
            (b/'request').write_text('visible')
            (b/'task').write_text(json.dumps({'id':'one','version':'1','condition':{'id':'ordinary','version':'1'},'request':'request','check':[sys.executable,'-c','print(\'{"functional":"pass","security":"pass"}\')']}))
            config={'executable':str(fake),'codex_home':str(b/'home'),'model':'default','reasoning_effort':'default','sandbox':'workspace-write','approval_policy':'never','network_access':True,'web_search':'live','clean_runtime_review':'fixture'}
            (b/'config').write_text(json.dumps(config))
            p=subprocess.run([sys.executable,'-m','principiis','run','--task',str(b/'task'),'--codex-config',str(b/'config'),'--output',str(b/'out')],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            result=json.loads((b/'out/result.json').read_text())
            self.assertEqual(result['outcome'],'joint_pass')
            self.assertIsNone(result['execution']['codex']['model'])

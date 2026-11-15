import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InvestigationCLI(unittest.TestCase):
    def test_separate_agent_and_executable_evidence_leave_primary_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = root / 'snapshot'
            snapshot.mkdir()
            (snapshot / 'seed.txt').write_text('engineering-only-seed')
            primary = root / 'primary.json'
            primary.write_text('{"functional":"pass","security":"pass"}')
            digest = hashlib.sha256(primary.read_bytes()).hexdigest()
            agent = root / 'agent.py'
            agent.write_text('import json,sys,pathlib\nrequest=json.load(sys.stdin)\npathlib.Path("seed.txt").write_text("agent mutation")\nassert request["prompt"] == "Investigate engineering seed"\nprint(json.dumps({"claims":[{"id":"a","root_cause":"seed","evidence":"yes"},{"id":"b","root_cause":"seed","evidence":"yes"},{"id":"c","root_cause":"absent","evidence":"no"},{"id":"d","root_cause":"unsupported","evidence":"missing"},{"id":"e","root_cause":"unrelated","evidence":"yes"}]}))\n')
            config = root / 'config.json'
            config.write_text(json.dumps({'version': 'fixture-1', 'model': 'simulated', 'settings': {},
                'agent': [sys.executable, str(agent)], 'timeout_seconds': 5,
                'evidence': {'yes': {'root_cause': 'seed', 'scope': 'engineering seed visible', 'argv': [sys.executable, '-c', 'import json,pathlib; print(json.dumps({"reproduced":pathlib.Path("seed.txt").read_text()=="engineering-only-seed"}))']},
                             'no': {'root_cause': 'absent', 'scope': 'engineering absent property', 'argv': [sys.executable, '-c', 'import json,pathlib; print(json.dumps({"reproduced":pathlib.Path("absent.txt").exists()}))']}}}))
            prompt = root / 'prompt.txt'
            prompt.write_text('Investigate engineering seed')
            output = root / 'investigation'
            command = [sys.executable, '-m', 'principiis.investigation', '--snapshot', str(snapshot),
                       '--primary', str(primary), '--config', str(config), '--prompt', str(prompt),
                       '--prompt-version', 'engineering-1', '--output', str(output)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((output / 'investigation.json').read_text())
            self.assertEqual([c['status'] for c in report['claims']], ['verified','verified','rejected','unresolved','unresolved'])
            self.assertEqual(report['verified_root_causes'], ['seed'])
            self.assertEqual(report['primary']['sha256'], digest)
            self.assertEqual(hashlib.sha256(primary.read_bytes()).hexdigest(), digest)
            self.assertEqual((snapshot / 'seed.txt').read_text(), 'engineering-only-seed')
            self.assertTrue((output / report['claims'][0]['evidence_ref']).is_file())
            self.assertEqual(report['resources']['scope'], 'independent_evaluation')
            self.assertIsNone(report['resources']['reported_tokens'])
            self.assertNotEqual(subprocess.run(command, cwd=ROOT, capture_output=True).returncode, 0)


    def test_failed_agent_retains_evidence_and_explicit_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'snapshot').mkdir()
            (root / 'primary.json').write_text('{}')
            (root / 'prompt.txt').write_text('engineering fixture')
            (root / 'config.json').write_text(json.dumps({
                'version': 'fixture', 'model': 'simulated', 'settings': {},
                'agent': [sys.executable, '-c', 'import sys; print("partial"); sys.exit(2)'],
                'timeout_seconds': 2, 'evidence': {}}))
            result = subprocess.run([sys.executable, '-m', 'principiis.investigation',
                '--snapshot', str(root / 'snapshot'), '--primary', str(root / 'primary.json'),
                '--config', str(root / 'config.json'), '--prompt', str(root / 'prompt.txt'),
                '--prompt-version', 'fixture', '--output', str(root / 'output')],
                cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((root / 'output/investigation.json').read_text())
            self.assertEqual(report['status'], 'evaluator_error')
            self.assertEqual(report['claims'], [])
            self.assertEqual(report['agent']['exit_status'], 2)
            self.assertIn('partial', (root / 'output/agent.stdout').read_text())
            self.assertTrue(report['primary']['unchanged'])


if __name__ == '__main__':
    unittest.main()

class CodexInvestigationCLI(unittest.TestCase):
    def test_subscription_evaluator_parses_final_claims_and_retains_usage_without_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            b=Path(d); (b/'snapshot').mkdir(); (b/'home').mkdir()
            (b/'primary').write_text('{}'); (b/'prompt').write_text('Investigate fixture')
            fake=b/'codex'
            fake.write_text('''#!/usr/bin/env python3
import json,sys
if sys.argv[1:] == ['--version']: print('fixture'); sys.exit()
assert '--model' not in sys.argv
assert 'Investigate fixture' in sys.stdin.read()
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'{"claims":[{"id":"one","root_cause":"fixture"}]}'}}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':4,'output_tokens':5}}))
'''); fake.chmod(0o755)
            codex={'executable':str(fake),'codex_home':str(b/'home'),'model':'default','reasoning_effort':'default','sandbox':'workspace-write','approval_policy':'never','network_access':True,'web_search':'live','clean_runtime_review':'fixture'}
            (b/'codex.json').write_text(json.dumps(codex))
            (b/'config').write_text(json.dumps({'version':'1','model':'default','settings':{},'codex_config':str(b/'codex.json'),'timeout_seconds':None,'evidence':{}}))
            p=subprocess.run([sys.executable,'-m','principiis.investigation','--snapshot',str(b/'snapshot'),'--primary',str(b/'primary'),'--config',str(b/'config'),'--prompt',str(b/'prompt'),'--prompt-version','1','--output',str(b/'out')],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            r=json.loads((b/'out/investigation.json').read_text())
            self.assertEqual(r['status'],'completed')
            self.assertEqual(r['claims'][0]['status'],'unresolved')
            self.assertEqual(r['resources']['reported_tokens']['total_tokens'],9)
            self.assertIn('turn.completed',(b/'out/agent.stdout').read_text())

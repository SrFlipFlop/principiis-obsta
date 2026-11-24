"""Evaluation-only imports retain source evidence without another development call."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import test_assessment_cli


class DerivedRunCLI(unittest.TestCase):
    def setUp(self):
        self.fixture = test_assessment_cli.QualifiedAssessmentCLI()
        self.fixture.setUp()
        self.addCleanup(self.fixture.temporary.cleanup)
        fixture = self.fixture
        docker = fixture.base/'unavailable-image-docker'
        docker.write_text('#!'+sys.executable+'\nimport sys\nsys.exit(0 if "rm" in sys.argv else 1)\n')
        docker.chmod(0o755)
        runtime = fixture.root/'runtime.json'
        runtime.write_text(json.dumps({'image':fixture.image,'docker':str(docker)}))
        fixture.configuration['frozen_files']['runtime.json'] = fixture.digest(runtime)
        fixture.configuration.update(run_name='run', run_mode='development-rehearsal',
            evaluator_binding='unbound', investigation='none',
            condition={'id':'ordinary','version':'1'})
        (fixture.root/'configuration.json').write_text(json.dumps(fixture.configuration))
        fixture.generate_checkpoint()
        self.assertEqual(fixture.cli('bind','--declaration',str(fixture.path)).returncode,0)
        # A prior bound primary must remain in the source run, never be imported.
        self.assertEqual(fixture.cli('evaluate','--step','step-01').returncode,0)
        fixture.declaration['version'] = 'engineering-corrected-2'
        fixture.publish()

    def cli(self, command, run, *arguments, success=True):
        fixture = self.fixture
        process = subprocess.run([sys.executable,'-m','principiis',command,
            '--run',run,'--runs-root',str(fixture.base),'--format','json',*arguments],
            cwd=fixture.source,capture_output=True,text=True)
        if success:
            self.assertEqual(process.returncode,0,process.stderr)
            return json.loads(process.stdout)
        self.assertNotEqual(process.returncode,0,process.stdout)
        return process

    def test_new_binding_uses_attested_snapshots_and_never_redevelops(self):
        fixture = self.fixture
        original = {path.relative_to(fixture.root):path.read_bytes() for path in fixture.root.rglob('*')
                    if path.is_file()}
        derived = self.cli('derive-evaluation','corrected','--source-run','run',
                           '--evaluator-manifest',str(fixture.path))
        destination = fixture.base/'corrected'
        self.assertEqual(derived['run_mode'],'evaluation-derived')
        self.assertEqual(derived['assessment_binding']['version'],'engineering-corrected-2')
        self.assertEqual(derived['source_run']['run_name'],'run')
        self.assertFalse((destination/'development/evaluations').exists())
        self.assertEqual(derived['checkpoints'][0]['status'],'pending_evaluation')
        self.assertIsNone(derived['checkpoints'][0]['primary_assessment'])
        self.assertIn('evaluation-only',self.cli('develop','corrected','--step','1',success=False).stderr)
        self.assertFalse((destination/'development/attempts').exists())
        first = self.cli('evaluate','corrected','--step','1')
        primary = first['checkpoints'][0]['primary_assessment']
        self.assertEqual(primary['role'],'primary')
        self.assertEqual(primary['provenance']['version'],'engineering-corrected-2')
        original_primary = (fixture.root/'development/evaluations/step-01/1/result.json').read_bytes()
        self.cli('evaluate','corrected','--step','1','--rerun')
        report = self.cli('report','corrected')
        self.assertEqual(len(report['assessments']),2)
        self.assertEqual(report['source_run']['run_name'],'run')
        self.assertEqual(report['resources']['totals']['development']['attempts_present'],1)
        self.assertEqual(report['resources']['totals']['evaluation']['attempts_present'],2)
        self.assertIn('Evaluation-only import of development run',
                      (destination/'reports/development.md').read_text())
        self.assertIn('source_run', (destination/'reports/development.csv').read_text().splitlines()[0])
        self.assertEqual((fixture.root/'development/evaluations/step-01/1/result.json').read_bytes(),original_primary)
        self.assertEqual({path.relative_to(fixture.root):path.read_bytes() for path in fixture.root.rglob('*')
                          if path.is_file()},original)

    def test_import_refuses_missing_or_incomplete_source_without_target(self):
        fixture = self.fixture
        source_result = fixture.root/'development/steps/step-01/result.json'
        source_result.unlink()
        rejected = self.cli('derive-evaluation','broken','--source-run','run',
            '--evaluator-manifest',str(fixture.path),success=False)
        self.assertIn('completed',rejected.stderr)
        self.assertFalse((fixture.base/'broken').exists())

    def test_imported_development_tamper_is_detected_without_changing_source(self):
        fixture = self.fixture
        self.cli('derive-evaluation','corrected','--source-run','run',
                 '--evaluator-manifest',str(fixture.path))
        imported = fixture.base/'corrected/development/steps/step-01/result.json'
        source = fixture.root/'development/steps/step-01/result.json'
        original = source.read_bytes()
        imported.write_bytes(imported.read_bytes()+b' ')
        rejected = self.cli('status','corrected',success=False)
        self.assertIn('imported development evidence changed',rejected.stderr)
        self.assertEqual(source.read_bytes(),original)

    def test_source_mutation_invalidates_derived_lineage(self):
        fixture = self.fixture
        self.cli('derive-evaluation','corrected','--source-run','run',
                 '--evaluator-manifest',str(fixture.path))
        source = fixture.root/'development/steps/step-01/result.json'
        source.write_bytes(source.read_bytes()+b' ')
        rejected = self.cli('status','corrected',success=False)
        self.assertIn('source development lineage changed',rejected.stderr)

    def test_new_package_version_cannot_relabel_old_development(self):
        fixture = self.fixture
        package = fixture.package/'package.json'
        metadata = json.loads(package.read_text())
        metadata['version'] = 'new-version-with-same-request-bytes'
        package.write_text(json.dumps(metadata))
        rejected = self.cli('derive-evaluation','corrected','--source-run','run',
            '--evaluator-manifest',str(fixture.path),success=False)
        self.assertIn('package version differs',rejected.stderr)
        self.assertFalse((fixture.base/'corrected').exists())

    def test_new_source_binding_invalidates_initially_unbound_lineage(self):
        fixture = self.fixture
        shutil.rmtree(fixture.root/'development/evaluations')
        for name in ('evaluator-binding.json','evaluator-manifest.json','evaluator-release.json'):
            (fixture.root/name).unlink()
        self.cli('derive-evaluation','corrected','--source-run','run',
                 '--evaluator-manifest',str(fixture.path))
        (fixture.root/'evaluator-binding.json').write_text('{}')
        rejected = self.cli('status','corrected',success=False)
        self.assertIn('source development lineage changed',rejected.stderr)

    def test_unresolved_source_evaluation_cleanup_blocks_import(self):
        fixture = self.fixture
        result = fixture.root/'development/evaluations/step-01/1/result.json'
        record = json.loads(result.read_text())
        record['cleanup_pending'] = True
        result.write_text(json.dumps(record))
        rejected = self.cli('derive-evaluation','corrected','--source-run','run',
            '--evaluator-manifest',str(fixture.path),success=False)
        self.assertIn('source evaluation runtime cleanup is unresolved',rejected.stderr)
        self.assertFalse((fixture.base/'corrected').exists())


if __name__ == '__main__':
    unittest.main()

"""Issue #75 item 3: evaluator files are found by SHA-256, and new runs carry their own copy."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import test_assessment_cli as fixtures


class EvaluatorLookup(unittest.TestCase):
    setUp = fixtures.QualifiedAssessmentCLI.setUp
    digest = staticmethod(fixtures.QualifiedAssessmentCLI.digest)
    publish = fixtures.QualifiedAssessmentCLI.publish
    cli = fixtures.QualifiedAssessmentCLI.cli
    generate_checkpoint = fixtures.QualifiedAssessmentCLI.generate_checkpoint

    def stub_docker(self):
        docker = self.base / 'unavailable-image-docker'
        docker.write_text('#!/usr/bin/python3\nimport sys\nargs=sys.argv[1:]\n'
                          "if args[:1]==['rm']: print('none')\nelse:\n print('unavailable',file=sys.stderr)\n raise SystemExit(1)\n")
        docker.chmod(0o755)
        runtime = self.root / 'runtime.json'
        runtime.write_text(json.dumps({'image': self.image, 'docker': str(docker)}))
        self.configuration['frozen_files']['runtime.json'] = self.digest(runtime)
        (self.root / 'configuration.json').write_text(json.dumps(self.configuration))
        self.generate_checkpoint()

    def binding(self):
        return json.loads((self.root / 'evaluator-binding.json').read_text())

    def bind(self):
        self.assertEqual(self.cli('bind', '--declaration', str(self.path)).returncode, 0)

    def make_old_record(self):
        """Rewrite a fresh binding into the pre-#75 format: absolute path, no run-local copy."""
        self.bind()
        old = self.binding()
        old.pop('source_manifest')
        old['manifest'] = str(self.path)
        (self.root / 'evaluator-binding.json').write_text(json.dumps(old))
        shutil.rmtree(self.root / 'evaluator')
        return (self.root / 'evaluator-binding.json').read_bytes()

    def evaluated(self, process):
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads((self.root / 'development/evaluations/step-01/1/result.json').read_text())

    def test_bind_copies_manifest_and_files_and_records_relative_fingerprint(self):
        self.bind()
        binding = self.binding()
        self.assertEqual(binding['manifest'], 'evaluator/bundle.json')
        self.assertEqual(binding['source_manifest'], str(self.path))
        self.assertEqual(binding['manifest_sha256'], self.digest(self.root / 'evaluator/bundle.json'))
        for name, expected in binding['files'].items():
            self.assertEqual(self.digest(self.root / 'evaluator' / name), expected)

    def test_new_run_evaluates_after_the_original_evaluator_is_gone(self):
        self.stub_docker()
        self.bind()
        shutil.rmtree(self.bundle)
        result = self.evaluated(self.cli('evaluate', '--step', 'step-01'))
        argv = result['evaluation']['argv']
        self.assertTrue(argv[argv.index('--check-contract') + 1].startswith(str(self.root / 'evaluator')))

    def test_tampered_run_copy_is_rejected_and_edited_original_is_irrelevant(self):
        self.stub_docker()
        self.bind()
        (self.bundle / 'preparation.json').write_text('original edited after binding')
        self.assertEqual(self.cli('inspect').returncode, 0)
        (self.root / 'evaluator/preparation.json').write_text('copy tampered')
        process = self.cli('evaluate', '--step', 'step-01')
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('dependency content changed', process.stderr)
        self.assertFalse((self.root / 'development/evaluations').exists())

    def test_old_record_evaluates_through_hash_lookup_after_path_is_gone(self):
        self.stub_docker()
        before = self.make_old_record()
        moved = self.base / 'moved'
        self.bundle.rename(moved)
        self.assertFalse(self.path.exists())
        missing = self.cli('evaluate', '--step', 'step-01')
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('not found by SHA-256', missing.stderr)
        self.assertFalse((self.root / 'development/evaluations').exists())
        result = self.evaluated(self.cli('evaluate', '--step', 'step-01', '--evaluator-root', str(self.base)))
        self.assertEqual(result['provenance']['manifest'], str(self.path))  # recorded, not rewritten
        argv = result['evaluation']['argv']
        self.assertTrue(argv[argv.index('--check-contract') + 1].startswith(str(moved)))
        self.assertEqual((self.root / 'evaluator-binding.json').read_bytes(), before)
        self.assertFalse((self.root / 'evaluator').exists())

    def test_old_record_found_through_environment_root(self):
        self.stub_docker()
        self.make_old_record()
        self.bundle.rename(self.base / 'elsewhere')
        env = dict(os.environ, PRINCIPIIS_EVALUATOR_ROOT=str(self.base))
        process = subprocess.run([sys.executable, '-m', 'principiis.assessment', 'evaluate', '--root',
                                  str(self.root), '--step', 'step-01'], cwd=self.source,
                                 capture_output=True, text=True, env=env)
        self.evaluated(process)

    def test_old_record_found_in_repository_evaluator_tree(self):
        self.stub_docker()
        self.make_old_record()
        (self.package / 'evaluator').mkdir()
        self.bundle.rename(self.package / 'evaluator/v1')
        self.evaluated(self.cli('evaluate', '--step', 'step-01'))

    def test_matching_hashes_win_over_same_named_decoy_in_other_root(self):
        self.stub_docker()
        self.make_old_record()
        decoy = self.base / 'a-decoy'
        shutil.copytree(self.bundle, decoy)
        (decoy / 'contract.json').write_text(json.dumps({'x': 'functional', 'y': 'security'}))
        self.bundle.rename(self.base / 'z-real')
        self.evaluated(self.cli('evaluate', '--step', 'step-01', '--evaluator-root', str(decoy),
                                '--evaluator-root', str(self.base / 'z-real')))

    def test_hash_mismatch_is_never_accepted(self):
        self.stub_docker()
        self.make_old_record()
        (self.bundle / 'seccomp.json').write_text('{"changed": true}')
        process = self.cli('evaluate', '--step', 'step-01')
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('not found by SHA-256', process.stderr)
        self.bundle.rename(self.base / 'moved')
        process = self.cli('evaluate', '--step', 'step-01', '--evaluator-root', str(self.base))
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse((self.root / 'development/evaluations').exists())

    def test_rebinding_same_evaluator_is_idempotent_and_different_one_is_refused(self):
        self.bind()
        first = (self.root / 'evaluator-binding.json').read_bytes()
        self.bind()
        self.assertEqual((self.root / 'evaluator-binding.json').read_bytes(), first)
        self.declaration['version'] = 'engineering-2'
        self.publish()
        self.assertNotEqual(self.cli('bind', '--declaration', str(self.path)).returncode, 0)


if __name__ == '__main__':
    unittest.main()

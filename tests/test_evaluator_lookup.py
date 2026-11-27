"""Issue #75 item 3: evaluator files are found by SHA-256, and new runs carry their own copy."""
import json
import os
import shutil
import unittest

import test_assessment_cli as fixtures
from principiis.assessment import RestrictedEvaluator
from principiis.run_store import RunStore


class EvaluatorLookup(unittest.TestCase):
    setUp = fixtures.QualifiedAssessmentCLI.setUp
    digest = staticmethod(fixtures.QualifiedAssessmentCLI.digest)
    publish = fixtures.QualifiedAssessmentCLI.publish
    make_run = fixtures.QualifiedAssessmentCLI.make_run
    bind = fixtures.QualifiedAssessmentCLI.bind
    operator = fixtures.QualifiedAssessmentCLI.operator
    generate_checkpoint = fixtures.QualifiedAssessmentCLI.generate_checkpoint

    def bound_run(self):
        """A run with one checkpoint whose restricted runner fails at the Docker boundary."""
        docker = self.base / 'unavailable-image-docker'
        docker.write_text("#!/usr/bin/python3\nimport sys\nargs=sys.argv[1:]\n"
                          "if args[:1]==['--host']: args=args[2:]\n"
                          "if args[:1]==['rm']: print('none')\nelse:\n print('unavailable',file=sys.stderr)\n raise SystemExit(1)\n")
        docker.chmod(0o755)
        self.make_run({'image': self.image, 'docker': str(docker)})
        self.generate_checkpoint()
        self.bind()

    def binding(self):
        return RunStore.open(self.root).binding

    def make_old_record(self):
        """Rewrite the fresh binding into the pre-#75 format: absolute path, no run-local copy."""
        self.bound_run()
        old = self.binding()
        old.pop('source_manifest')
        old['manifest'] = str(self.path)
        (self.root / 'evaluator-binding.json').write_text(json.dumps(old))
        shutil.rmtree(self.root / 'evaluator')
        self.assertEqual(self.binding()['manifest'], str(self.path))

    def evaluate(self, *arguments, success=True, **options):
        process = self.operator('evaluate', '--step', '1', *arguments, success=success, **options)
        return process['assessments'][0] if success else process

    def assert_evaluated(self, assessment):
        # The restricted runner started and failed only at the stubbed Docker boundary.
        self.assertEqual(assessment['outcome'], 'evaluator_error')
        self.assertTrue(assessment['runtime_launch_attempted'] or assessment['evaluation']['elapsed_seconds'] > 0)

    def test_bind_copies_manifest_and_files_and_records_relative_fingerprint(self):
        self.bound_run()
        binding = self.binding()
        self.assertEqual(binding['manifest'], 'evaluator/bundle.json')
        self.assertEqual(binding['source_manifest'], str(self.path))
        self.assertEqual(binding['manifest_sha256'], self.digest(self.root / 'evaluator/bundle.json'))
        for name, expected in binding['files'].items():
            self.assertEqual(self.digest(self.root / 'evaluator' / name), expected)
        self.assertEqual(self.operator('status')['assessment_binding']['manifest'], 'evaluator/bundle.json')

    def test_new_run_evaluates_after_the_original_evaluator_is_gone(self):
        self.bound_run()
        shutil.rmtree(self.bundle)
        self.assertEqual(RestrictedEvaluator(self.binding(), 'docker', root=self.root).directory,
                         self.root / 'evaluator')
        self.assert_evaluated(self.evaluate())

    def test_editing_the_original_after_binding_is_irrelevant(self):
        self.bound_run()
        (self.bundle / 'contract.json').write_text(json.dumps({'other': 'functional', 'denial': 'security'}))
        self.assertEqual(self.operator('status')['assessments'], [])
        self.assert_evaluated(self.evaluate())

    def test_tampered_run_copy_is_rejected_before_allocating(self):
        self.bound_run()
        (self.root / 'evaluator/contract.json').write_text(json.dumps({'other': 'functional', 'denial': 'security'}))
        process = self.evaluate(success=False)
        self.assertIn('dependency content changed', process.stderr)
        self.assertEqual(self.operator('status')['assessments'], [])

    def test_tampered_run_copy_of_the_manifest_is_rejected(self):
        self.bound_run()
        (self.root / 'evaluator/bundle.json').write_text('{}')
        process = self.evaluate(success=False)
        self.assertIn('manifest content changed', process.stderr)
        self.assertEqual(self.operator('status')['assessments'], [])

    def test_old_record_evaluates_through_hash_lookup_after_path_is_gone(self):
        self.make_old_record()
        before = (self.root / 'evaluator-binding.json').read_bytes()
        moved = self.base / 'moved'
        self.bundle.rename(moved)
        missing = self.evaluate(success=False)
        self.assertIn('not found by SHA-256', missing.stderr)
        self.assertEqual(self.operator('status')['assessments'], [])
        self.assertEqual(RestrictedEvaluator(self.binding(), 'docker', root=self.root,
                                             search_roots=[self.base]).directory, moved)
        self.assert_evaluated(self.evaluate('--evaluator-root', str(self.base)))
        self.assertEqual((self.root / 'evaluator-binding.json').read_bytes(), before)  # recorded, not rewritten
        self.assertEqual(self.binding()['manifest'], str(self.path))
        self.assertFalse((self.root / 'evaluator').exists())

    def test_old_record_found_through_environment_root(self):
        self.make_old_record()
        self.bundle.rename(self.base / 'elsewhere')
        self.assert_evaluated(self.evaluate(env=dict(os.environ, PRINCIPIIS_EVALUATOR_ROOT=str(self.base))))

    def test_old_record_found_in_repository_evaluator_tree(self):
        self.make_old_record()
        (self.package / 'evaluator').mkdir()
        self.bundle.rename(self.package / 'evaluator/v1')
        self.assert_evaluated(self.evaluate())

    def test_matching_hashes_win_over_same_named_decoy_in_other_root(self):
        self.make_old_record()
        decoy = self.base / 'a-decoy'
        shutil.copytree(self.bundle, decoy)
        (decoy / 'contract.json').write_text(json.dumps({'x': 'functional', 'y': 'security'}))
        self.bundle.rename(self.base / 'z-real')
        self.assert_evaluated(self.evaluate('--evaluator-root', str(decoy),
                                            '--evaluator-root', str(self.base / 'z-real')))

    def test_hash_mismatch_is_never_accepted(self):
        self.make_old_record()
        (self.bundle / 'seccomp.json').write_text('{"changed": true}')
        process = self.evaluate(success=False)
        self.assertIn('not found by SHA-256', process.stderr)
        self.bundle.rename(self.base / 'moved')
        process = self.evaluate('--evaluator-root', str(self.base), success=False)
        self.assertIn('not found by SHA-256', process.stderr)
        self.assertEqual(self.operator('status')['assessments'], [])

    def test_rebinding_same_evaluator_is_idempotent_and_different_one_is_refused(self):
        self.bound_run()
        first = (self.root / 'evaluator-binding.json').read_bytes()
        self.bind()
        self.assertEqual((self.root / 'evaluator-binding.json').read_bytes(), first)
        self.declaration['version'] = 'engineering-2'
        self.publish()
        with self.assertRaisesRegex(ValueError, 'evaluator binding changed'):
            self.bind()


if __name__ == '__main__':
    unittest.main()

"""Comparison counts only retained primary assessments with matching contracts."""
import unittest

from principiis.comparison import compare_reports


def report(run, condition, outcomes, package='frozen-package', evaluator='frozen-checker'):
    return {
        'run_name': run, 'application': 'document-portal', 'package_version': 'v3',
        'condition': {'id': condition, 'version': '1'},
        'package_sha256': package, 'run_mode': 'qualification',
        'assessment_binding': {'manifest_sha256': evaluator},
        'checkpoints': [{
            'id': f'step-{number:02}',
            'primary_assessment': {'functional': functional, 'security': security,
                                   'outcome': 'joint_pass' if functional == security == 'pass' else 'candidate_failure'}
            if functional is not None else None,
        } for number, (functional, security) in enumerate(outcomes, 1)],
        'resources': {'totals': {'development': {'duration_seconds': 12},
                                 'evaluation': {'duration_seconds': 4}}},
    }


class ComparisonTests(unittest.TestCase):
    def test_joint_pass_and_missing_are_distinct(self):
        compared = compare_reports([
            report('ordinary', 'baseline', [('pass', 'pass'), ('pass', 'fail')]),
            report('review', 'review', [('pass', 'pass'), (None, None)]),
        ])
        self.assertEqual(compared['runs'][0]['joint_pass_checkpoints'], 1)
        self.assertEqual(compared['runs'][0]['security_fail_checkpoints'], 1)
        self.assertEqual(compared['runs'][1]['unassessable_checkpoints'], 1)
        self.assertFalse(compared['complete'])

    def test_different_evaluator_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'same frozen'):
            compare_reports([
                report('a', 'baseline', [('pass', 'pass')]),
                report('b', 'review', [('pass', 'pass')], evaluator='changed'),
            ])


if __name__ == '__main__':
    unittest.main()

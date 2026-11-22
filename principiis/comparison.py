"""Compare compatible run evidence without treating checkpoints as independent trials."""
import csv
import io


def compare_reports(reports):
    if len(reports) < 2:
        raise ValueError('compare requires at least two runs')
    reference = reports[0]
    if not reference.get('assessment_binding'):
        raise ValueError('compared runs require a bound evaluator')
    required = (reference['application'], reference['package_sha256'],
                reference['assessment_binding']['manifest_sha256'],
                tuple(item['id'] for item in reference['checkpoints']))
    rows = []
    for report in reports:
        binding = report.get('assessment_binding')
        actual = (report.get('application'), report.get('package_sha256'),
                  binding.get('manifest_sha256') if binding else None,
                  tuple(item['id'] for item in report['checkpoints']))
        if report.get('run_mode') != 'qualification' or actual != required:
            raise ValueError('compared runs require the same frozen application, requests and evaluator')
        outcomes = []
        for checkpoint in report['checkpoints']:
            assessment = checkpoint.get('primary_assessment')
            functional = assessment.get('functional') if assessment else None
            security = assessment.get('security') if assessment else None
            outcomes.append({'step': checkpoint['id'], 'functional': functional,
                             'security': security, 'joint_pass': functional == security == 'pass',
                             'assessment': assessment.get('outcome') if assessment else None})
        rows.append({
            'run': report['run_name'], 'condition': report.get('condition'),
            'joint_pass_checkpoints': sum(row['joint_pass'] for row in outcomes),
            'functional_fail_checkpoints': sum(row['functional'] == 'fail' for row in outcomes),
            'security_fail_checkpoints': sum(row['security'] == 'fail' for row in outcomes),
            'unassessable_checkpoints': sum(row['functional'] not in ('pass', 'fail')
                                             or row['security'] not in ('pass', 'fail') for row in outcomes),
            'supplemental_verified_root_causes': len({cause
                for entry in report.get('investigations', [])
                if entry.get('artifact', '').endswith('/1/investigation.json')
                for cause in entry.get('verified_root_causes') or []}),
            'supplemental_unresolved_claims': sum(
                sum(claim.get('status') == 'unresolved' for claim in entry.get('claims', []))
                for entry in report.get('investigations', [])
                if entry.get('artifact', '').endswith('/1/investigation.json')),
            'checkpoints': outcomes, 'resource_totals': report['resources']['totals'],
        })
    return {'application': reference['application'], 'package_version': reference['package_version'],
            'package_sha256': required[1], 'evaluator_manifest_sha256': required[2],
            'complete': all(all(row['assessment'] is not None for row in run['checkpoints']) for run in rows),
            'runs': rows,
            'interpretation': 'Checkpoints within an application are dependent; these counts are descriptive, not independent samples.'}


def markdown(result):
    lines = [f"Comparison: {result['application']} @ {result['package_version']}", '',
             '| Run | Condition | Joint pass | Functional fail | Security fail | Unassessable | Supplemental verified | Unresolved claims |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for row in result['runs']:
        condition = row['condition'] or {}
        lines.append(f"| {row['run']} | {condition.get('id', 'unknown')} | {row['joint_pass_checkpoints']} | "
                     f"{row['functional_fail_checkpoints']} | {row['security_fail_checkpoints']} | "
                     f"{row['unassessable_checkpoints']} | {row['supplemental_verified_root_causes']} | "
                     f"{row['supplemental_unresolved_claims']} |")
    lines.extend(['', result['interpretation'],
                  'Complete primary assessments: ' + ('yes' if result['complete'] else 'no')])
    return '\n'.join(lines) + '\n'


def csv_report(result):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=('run', 'condition', 'step', 'functional', 'security', 'joint_pass', 'assessment'))
    writer.writeheader()
    for run in result['runs']:
        for checkpoint in run['checkpoints']:
            writer.writerow({'run': run['run'], 'condition': (run['condition'] or {}).get('id'), **checkpoint})
    return stream.getvalue()

"""Readable run reports: markdown, CSV and command summaries, plus comparison tables.

Every function takes the status dictionary built by `principiis.status.build`
(or a comparison from `principiis.comparison.compare_reports`) and returns text.
"""
import csv
import io
import json
from pathlib import Path
import shlex

from . import resource


def display(value):
    return 'unknown' if value is None else str(value)


def markdown(report):
    binding = report.get('assessment_binding')
    evaluator = binding['version'] if binding else report['evaluator_binding']
    lines = ['## Run', '', f"Run: {report['run_name']} ({report['run_mode']})", '',
             f"Application: {report['application']} @ {report['package_version']}",
             f"Condition: {(report.get('condition') or {}).get('id', 'unknown')}",
             f"Investigation: {report.get('investigation', 'not configured')}",
             f"Evaluator: {evaluator}" + ('.' if binding else '; primary scores unavailable.'),
             f"Artifacts: {report['root']}", '', '## Checkpoints', '',
             '| Checkpoint | Development | Evaluation | Attempts | Retained source |',
             '| --- | --- | --- | --- | --- |']
    if report.get('source_run'):
        source = report['source_run']
        lines[lines.index('## Checkpoints'):lines.index('## Checkpoints')] = [
            f"Evaluation-only import of development run {source['run_name']} ({source['root']}); "
            'development measurements are copied evidence, not new model usage.', '']
    for checkpoint in report['checkpoints']:
        development = 'finished' if checkpoint['status'] == 'pending_evaluation' else checkpoint['status']
        primary = checkpoint.get('primary_assessment')
        evaluation = primary['outcome'] if primary else 'not run'
        lines.append(f"| {checkpoint['id']} | {development} | {evaluation} | {checkpoint['attempts']} | {display(checkpoint['source'])} |")
    log_lines = []
    for checkpoint in report['checkpoints']:
        if checkpoint['stdout']:
            log_lines.extend([f"{checkpoint['id']} Codex events: {checkpoint['stdout']}",
                              f"{checkpoint['id']} errors: {checkpoint['stderr']}"])
    if log_lines:
        lines.extend(['', '## Logs', '', *log_lines])
    assessments = report.get('assessments', [])
    if assessments:
        lines.extend(['', '## Hidden evaluations', '', '| Checkpoint | Assessment | Role | Functional | Security | Outcome | Evidence |',
                      '| --- | --- | --- | --- | --- | --- | --- |'])
        for assessment in assessments:
            lines.append(f"| {assessment['checkpoint']} | {assessment['attempt']} | {assessment['role']} | "
                         f"{assessment['functional']} | {assessment['security']} | {assessment['outcome']} | {assessment['artifact']} |")
        details = []
        for assessment in assessments:
            if assessment.get('error'):
                details.append(f"- {assessment['checkpoint']} assessment {assessment['attempt']}: "
                               + ' '.join(str(assessment['error']).split()))
            for check in assessment.get('checks', []):
                if check['status'] != 'pass':
                    reason = ' '.join(str(check.get('detail', '')).split())
                    details.append(f"- {assessment['checkpoint']} assessment {assessment['attempt']} "
                                   f"{check['id']}: {check['status']}" + (f' — {reason}' if reason else ''))
        if details:
            lines.extend(['', '### Evaluation details', '', *details])
    if report.get('investigations'):
        lines.extend(['', '## AI reviews', '', '| Checkpoint | Investigation | Claims | Verified root causes | Seconds | Tokens | Evidence |',
                      '| --- | --- | ---: | ---: | ---: | ---: | --- |'])
        for entry in report['investigations']:
            resources = entry.get('resources') or {}
            tokens = resources.get('reported_tokens') or {}
            lines.append(f"| {entry['checkpoint']} | {entry['status']} | {len(entry['claims'])} | "
                         f"{len(entry['verified_root_causes'])} | {display(resources.get('elapsed_seconds'))} | "
                         f"{display(tokens.get('total_tokens'))} | {entry['artifact']} |")
    lines.extend(['', resource.markdown(report['resources']).rstrip()])
    for entry in report['runtime_cleanup_required']:
        lines.extend(['', f"Runtime cleanup pending for {entry['step']}: {entry['allocation']}",
                      f"Cleanup: python3 -m principiis cleanup --runs-root {Path(report['root']).parent} "
                      f"--run {report['run_name']} --step {entry['step']}"])
    for entry in report.get('evaluation_cleanup_required', []):
        lines.extend(['', f"Evaluation cleanup pending: {entry['artifact']}",
                      f"Cleanup: python3 -m principiis cleanup-evaluation --runs-root {Path(report['root']).parent} "
                      f"--run {report['run_name']} --step {entry['checkpoint']}"])
    for entry in report.get('investigation_cleanup_required', []):
        lines.extend(['', f"Investigation cleanup pending: {entry['allocation']}",
                      f"Cleanup: principiis cleanup-investigation --runs-root {Path(report['root']).parent} "
                      f"--run {report['run_name']} --step {entry['step']}"])
    for entry in report['previews']:
        evidence = entry['evidence'] or {}
        lines.extend(['', f"{entry['step']} preview evidence: {report['root']}/{entry['artifact']}",
                      f"Preview: {evidence.get('outcome', 'unknown')} ; URL: {display(evidence.get('url'))}",
                      f"Cleanup: python3 -m principiis preview --runs-root {Path(report['root']).parent} "
                      f"--run {report['run_name']} --step {entry['step']} --stop"])
    action = report['next_action']
    lines.extend(['', '## Next action', '',
                  action['action'] + (' ' + action['step'] if action['step'] else ''), action['explanation']])
    if action['action'] in ('develop', 'retry', 'evaluate') and action['step']:
        number = int(action['step'].split('-')[-1])
        command = 'develop' if action['action'] in ('develop', 'retry') else 'evaluate'
        retry = ' --retry' if action['action'] == 'retry' else ''
        runs_root = shlex.quote(str(Path(report['root']).parent))
        lines.append(f"Command: principiis {command} --runs-root {runs_root} "
                     f"--run {report['run_name']} --step {number}{retry}")
    return '\n'.join(lines) + '\n'


def development_summary(report, step):
    """Show the result of this development action without repeating the full run report."""
    checkpoint = next(entry for entry in report['checkpoints'] if entry['id'] == step)
    completed = checkpoint['completed']
    lines = [f"Development {step}: {'completed' if completed else checkpoint['status']}"]
    if checkpoint['source']:
        lines.append(f"{'Saved snapshot' if completed else 'Retained workspace'}: {checkpoint['source']}")
    lines.append('Evaluation: not run by this command')
    action = report['next_action']
    if action['action'] in ('develop', 'retry', 'evaluate') and action['step']:
        command = 'develop' if action['action'] in ('develop', 'retry') else 'evaluate'
        number = int(action['step'].split('-')[-1])
        retry = ' --retry' if action['action'] == 'retry' else ''
        label = 'Next in the bound evaluator sequence' if command == 'evaluate' else 'Next'
        lines.append(f"{label}: principiis {command} --runs-root "
                     f"{shlex.quote(str(Path(report['root']).parent))} --run {report['run_name']} "
                     f"--step {number}{retry}")
    else:
        lines.append(f"Operator next action: {action['action']} — {action['explanation']}")
    lines.append(f"Full status: principiis status --runs-root "
                 f"{shlex.quote(str(Path(report['root']).parent))} --run {report['run_name']}")
    return '\n'.join(lines) + '\n'


CSV_FIELDS = ('run_name', 'source_run', 'run_id', 'checkpoint', 'attempt', 'session_id', 'outcome', 'artifact',
              'stage', 'role', 'functional', 'security', 'evaluator_version', 'evaluator_manifest_sha256',
              'snapshot_manifest_sha256', 'source', 'stdout', 'stderr', 'development_seconds', 'evaluation_seconds', 'investigation_seconds', 'started_at', 'finished_at',
              *resource.CATEGORIES, 'total_tokens', 'local_peak_sampled_rss_bytes', 'local_memory_scope',
              'container_peak_sampled_bytes', 'container_memory_scope', 'actual_spending', 'hosted_model_memory')


def csv_report(report):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
    writer.writeheader()
    assessments = {entry['artifact']: entry for entry in report.get('assessments', [])}
    for attempt in report['resources']['attempts']:
        stage = 'evaluation' if attempt['stages']['evaluation'] and not attempt['stages']['development'] else 'development'
        evidence = attempt['stages'][stage]
        tokens, memory = evidence.get('tokens') or {}, evidence.get('memory') or {}
        container_memory = evidence.get('container_memory') or {}
        directory = Path(attempt['artifact']).parent
        result = assessments.get(attempt['artifact'])
        if result is None:
            result = json.loads(Path(attempt['artifact']).read_text()) if Path(attempt['artifact']).is_file() else {}
        row = {key: attempt.get(key) for key in ('run_id', 'checkpoint', 'attempt', 'session_id', 'outcome', 'artifact')}
        provenance = result.get('provenance') or {}
        row.update(run_name=report['run_name'], source_run=(report.get('source_run') or {}).get('run_name'),
                   stage=stage, role=result.get('role'),
                   functional=result.get('functional'), security=result.get('security'),
                   evaluator_version=provenance.get('version'), evaluator_manifest_sha256=provenance.get('manifest_sha256'),
                   snapshot_manifest_sha256=result.get('snapshot_manifest_sha256'),
                   source=result.get('snapshot') if stage == 'evaluation' else str(directory / ('snapshot' if result.get('completed') else 'workspace')),
                   stdout=str(directory / ('evaluator.stdout' if stage == 'evaluation' else 'executor.stdout')),
                   stderr=str(directory / ('evaluator.stderr' if stage == 'evaluation' else 'executor.stderr')),
                   development_seconds=evidence.get('elapsed_seconds') if stage == 'development' else None,
                   evaluation_seconds=evidence.get('elapsed_seconds') if stage == 'evaluation' else None,
                   started_at=evidence.get('started_at'),
                   finished_at=evidence.get('finished_at'), local_peak_sampled_rss_bytes=memory.get('peak_sampled_rss_bytes'),
                   local_memory_scope=memory.get('scope'), container_peak_sampled_bytes=container_memory.get('peak_sampled_bytes'),
                   container_memory_scope=container_memory.get('scope'), actual_spending=None, hosted_model_memory=None)
        row.update({key: tokens.get(key) for key in (*resource.CATEGORIES, 'total_tokens')})
        writer.writerow({key: display(value) for key, value in row.items()})
    for investigation in report.get('investigations', []):
        agent = investigation.get('agent') or {}
        tokens = (investigation.get('resources') or {}).get('reported_tokens') or {}
        memory = agent.get('memory') or {}
        directory = Path(investigation['artifact']).parent
        row = dict(run_name=report['run_name'], source_run=(report.get('source_run') or {}).get('run_name'),
                   run_id=report.get('run_id'), checkpoint=investigation['checkpoint'],
                   attempt=directory.name, session_id=None, outcome=investigation['status'],
                   artifact=investigation['artifact'], stage='investigation',
                   role='primary' if directory.name == '1' else 'rerun',
                   source=investigation.get('snapshot'), stdout=str(directory / 'agent.stdout'),
                   stderr=str(directory / 'agent.stderr'),
                   investigation_seconds=(investigation.get('resources') or {}).get('elapsed_seconds'),
                   started_at=agent.get('started_at'), finished_at=agent.get('finished_at'),
                   local_peak_sampled_rss_bytes=memory.get('peak_sampled_rss_bytes'),
                   local_memory_scope=memory.get('scope'), actual_spending=None, hosted_model_memory=None)
        row.update({key: tokens.get(key) for key in (*resource.CATEGORIES, 'total_tokens')})
        writer.writerow({key: display(row.get(key)) for key in CSV_FIELDS})
    return stream.getvalue()


def files(report):
    """The saved report set: JSON, CSV and markdown."""
    return {'development.json': json.dumps(report, indent=2) + '\n', 'development.csv': csv_report(report),
            'development.md': markdown(report)}


def outcome_details(report, command, step, *, ai_review=False):
    if command == 'develop':
        checkpoint = next((entry for entry in report['checkpoints'] if entry['id'] == step), None)
        return {'outcome': checkpoint['status'], 'artifact': checkpoint['result']} if checkpoint else {}
    if command == 'evaluate' and not ai_review:
        assessments = [entry for entry in report['assessments'] if entry['checkpoint'] == step]
        return {'outcome': assessments[-1]['outcome'], 'artifact': assessments[-1]['artifact']} if assessments else {}
    if command == 'evaluate' and ai_review:
        investigations = [entry for entry in report['investigations'] if entry['checkpoint'] == step]
        return {'outcome': investigations[-1]['status'], 'artifact': investigations[-1]['artifact']} if investigations else {}
    return {}


def comparison_markdown(result):
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


def comparison_csv(result):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=('run', 'condition', 'step', 'functional', 'security', 'joint_pass', 'assessment'))
    writer.writeheader()
    for run in result['runs']:
        for checkpoint in run['checkpoints']:
            writer.writerow({'run': run['run'], 'condition': (run['condition'] or {}).get('id'), **checkpoint})
    return stream.getvalue()

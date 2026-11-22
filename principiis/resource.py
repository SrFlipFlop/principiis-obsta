"""Passive measurements and artifact-only inspection; never invokes a model."""
import argparse
import json
from pathlib import Path

# Compatibility for existing callers of the measured execution seam.
from .execution import execute


CATEGORIES = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens')


def token_usage(path):
    """Only turn.completed usage is additive. Category subsets are never added twice."""
    totals = {key: 0 for key in CATEGORIES}
    known = {key: True for key in CATEGORIES}
    seen = set()
    found = False
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(event, dict) or event.get('type') != 'turn.completed':
            continue
        identity = event.get('id') or event.get('turn_id')
        if identity is not None:
            if identity in seen:
                continue
            seen.add(identity)
        usage = event.get('usage')
        if not isinstance(usage, dict):
            continue
        found = True
        for key in CATEGORIES:
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                totals[key] += value
            else:
                known[key] = False
    if not found:
        return None
    result = {key: totals[key] if known[key] else None for key in CATEGORIES}
    result['total_tokens'] = (totals['input_tokens'] + totals['output_tokens']
                              if known['input_tokens'] and known['output_tokens'] else None)
    return result


def inspect(root, *, result_paths=None):
    root = Path(root)
    paths = (list(result_paths) if result_paths is not None else
             [root / 'result.json'] if (root / 'result.json').is_file() else sorted(root.rglob('result.json')))
    attempts = []
    seen = {}
    for path in paths:
        result = json.loads(path.read_text())
        identity = (result['run_id'], result['session_id'])
        dedup_identity = identity if all(identity) else ('unknown allocation', str(path.resolve()))
        if dedup_identity in seen:
            if result != seen[dedup_identity]:
                raise ValueError('conflicting evidence for the same run/session')
            continue
        seen[dedup_identity] = result
        stages = {}
        for stage, key, log in [('development', 'execution', 'executor.stdout'), ('evaluation', 'evaluation', 'evaluator.stdout')]:
            evidence = result.get(key, {})
            # Initial result artifacts precede process launch. Missing final execution
            # metadata must not discard an attempt or its already emitted usage.
            present = (stage == 'development' and result.get('stage') != 'independent_evaluation') or bool(evidence)
            stages[stage] = dict(evidence, tokens=token_usage(path.parent / log) if stage == 'development' else evidence.get('tokens')) if present else {}
        attempts.append({'run_id': identity[0], 'session_id': identity[1], 'checkpoint': result['checkpoint'],
                         'attempt': result['attempt'], 'outcome': result['outcome'], 'artifact': str(path), 'stages': stages})
    return summarize(attempts)


def summarize(attempts):
    """Aggregate already selected controller records, including incomplete allocations."""
    totals = {}
    durations = []
    starts, ends = [], []
    for stage in ('development', 'evaluation'):
        entries = [attempt['stages'][stage] for attempt in attempts if attempt['stages'][stage]]
        values = [entry.get('elapsed_seconds') for entry in entries]
        durations.extend(values)
        tokens = [entry.get('tokens') for entry in entries]
        combined = None
        if tokens:
            combined = {key: (sum(value[key] for value in tokens) if all(value is not None and value.get(key) is not None for value in tokens) else None)
                        for key in (*CATEGORIES, 'total_tokens')}
            if all(value is None for value in combined.values()):
                combined = None
        totals[stage] = {'duration_seconds': sum(values) if values and None not in values else None, 'tokens': combined,
                         'attempts_present': len(entries), 'durations_measured': sum(value is not None for value in values)}
        starts.extend(entry['started_at'] for entry in entries if entry.get('started_at') is not None)
        ends.extend(entry['finished_at'] for entry in entries if entry.get('finished_at') is not None)
    measured = sum(len([a for a in attempts if a['stages'][stage]]) for stage in ('development', 'evaluation'))
    totals['stage_duration_seconds'] = sum(durations) if durations and None not in durations else None
    totals['wall_elapsed_seconds'] = max(ends) - min(starts) if starts and len(starts) == len(ends) == measured else None
    return {'schema_version': 1, 'attempts': attempts, 'totals': totals,
            'actual_spending': None, 'api_equivalent_estimate': None,
            'limitations': ['Cached input is a subset of input; reasoning output is a subset of output.',
                            'Missing categories remain unknown; token totals are input plus output only.',
                            'Only turn.completed events are additive; repeated explicit event IDs count once. Events without IDs count per line.',
                            'Wall span includes idle gaps; stage durations may overlap. Wall span is unknown without all stage timestamps.',
                            'Actual subscription spending is unknown. No API price assumption or incurred bill is inferred.',
                            'Hosted model RAM is not observable; local memory methodology is recorded per stage.']}



def markdown(report):
    def display(value):
        return 'unknown' if value is None else str(value)
    def seconds(value):
        return 'unknown' if value is None else f'{value:.1f}'
    lines = ['## Attempt measurements', '', '| Checkpoint | Attempt | Outcome | Stage | Seconds | Reported tokens | Host peak RSS (bytes) |',
             '| --- | --- | --- | --- | --- | --- | --- |']
    for attempt in report['attempts']:
        for stage, evidence in attempt['stages'].items():
            if not evidence:
                continue
            tokens = evidence.get('tokens')
            count = tokens.get('total_tokens') if tokens else None
            lines.append(f"| {attempt['checkpoint']} | {attempt['attempt']} | {attempt['outcome']} | {stage} | {seconds(evidence.get('elapsed_seconds'))} | {f'{count:,}' if count is not None else 'unknown'} | {display(evidence.get('memory', {}).get('peak_sampled_rss_bytes'))} |")
    lines.extend(['', '## Time and token totals', '',
                  'Wall time, including idle gaps: ' + seconds(report['totals']['wall_elapsed_seconds']) + ' seconds',
                  'Active stage time, all attempts: ' + seconds(report['totals']['stage_duration_seconds']) + ' seconds'])
    for stage in ('development', 'evaluation'):
        evidence = [attempt['stages'][stage] for attempt in report['attempts'] if attempt['stages'][stage]]
        measured = [entry['tokens']['total_tokens'] for entry in evidence
                    if entry.get('tokens') and entry['tokens'].get('total_tokens') is not None]
        label = stage.capitalize() + ' tokens: '
        if not evidence:
            lines.append(label + 'no attempts yet')
        elif len(measured) == len(evidence):
            lines.append(label + f'{sum(measured):,} reported across {len(evidence)} attempts')
        elif measured:
            lines.append(label + f'{sum(measured):,} measured across {len(measured)} of {len(evidence)} attempts; full total unknown')
        else:
            lines.append(label + f'unknown; no usable token record from {len(evidence)} attempt(s)')
    lines.extend(['Actual spending: unknown', 'API-equivalent estimate: unknown', '',
                  '## Measurement notes', '',
                  'Tokens come from Codex turn.completed records. Input plus output gives the reported total;',
                  'Cached input is a subset of input; reasoning output is a subset of output.',
                  'Missing usage stays unknown. Wall time includes idle gaps and is different from active stage time.',
                  'Host memory samples cover the Docker client process group, not the whole container or hosted model.'])
    for attempt in report['attempts']:
        for stage, evidence in attempt['stages'].items():
            container_memory = evidence.get('container_memory') or {}
            peak = container_memory.get('peak_sampled_bytes')
            if peak is not None:
                lines.append(f"{attempt['checkpoint']} attempt {attempt['attempt']} container peak: {peak:,} bytes (sampled working set)")
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description='Inspect retained resource evidence without running agents')
    parser.add_argument('artifacts')
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    args = parser.parse_args()
    report = inspect(args.artifacts)
    print(markdown(report) if args.format == 'markdown' else json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

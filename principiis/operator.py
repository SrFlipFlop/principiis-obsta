"""Principiis operator CLI: init a run, then develop and evaluate each step manually."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import time
import uuid

from . import pipeline, reporting, status
from .run_store import RunStore, digest, run_directory

RUNS_ROOT = os.environ.get('PRINCIPIIS_RUNS_ROOT', str(Path.home() / '.local/share/principiis/runs'))


def open_run(args, run=None):
    run = run or args.run
    return RunStore.open(run_directory(args.runs_root, run), run_name=run)


def step_identity(selection):
    from .benchmark import step_id
    match = re.fullmatch(r'(?:step-)?0*([1-9][0-9]*)', selection or '')
    if not match or (selection.startswith('step-') and step_id(int(match[1])) != selection):
        raise ValueError('select a request number such as 1 or step-01')
    return step_id(int(match[1]))


def selected_step(store, selection):
    step = step_identity(selection)
    if step not in store.step_ids:
        raise ValueError('selected checkpoint is outside the frozen run; use a new run for a longer sequence')
    return step


def require_no_cleanup(report, stage):
    if report['runtime_cleanup_required'] or report['evaluation_cleanup_required'] or report['investigation_cleanup_required']:
        raise ValueError(f'retained runtime requires explicit cleanup before further {stage}')


def initialize(args):
    from . import benchmark
    from .conditions import load as load_condition
    from .development_runtime import load_config
    runtime_path = Path(args.runtime_config).resolve()
    load_config(runtime_path)  # Validate configuration without starting Docker.
    condition_path, condition = load_condition(args.condition)
    root = run_directory(args.runs_root, args.run)
    metadata = benchmark.load(args.application)
    limit = benchmark.qualified_through(metadata)
    count = limit if args.steps is None else args.steps
    if not 1 <= count <= limit:
        raise ValueError(f'{args.application} evaluator is qualified through step {limit}; choose --steps 1 to {limit}')
    full_sequence = count == metadata['steps']
    if full_sequence and not args.evaluator_manifest:
        raise ValueError('a full-sequence run requires --evaluator-manifest during init')
    requests = dict(benchmark.requests(args.application, metadata, count))
    sequence = {'id': args.application, 'version': metadata['version'],
                'condition': {'id': condition['id'], 'version': condition['version']},
                'steps': [{'id': benchmark.step_id(n), 'version': metadata['version'], 'sequence_version': metadata['version'],
                           'request': benchmark.request_name(n)} for n in range(1, count + 1)]}
    configuration = {
        'schema_version': 1, 'run_name': args.run, 'application': args.application, 'condition': sequence['condition'],
        'run_mode': 'qualification' if full_sequence else 'development-rehearsal', 'evaluator_binding': 'unbound',
        'investigation': args.investigation, 'package_version': metadata['version'],
        'package_sha256': digest(benchmark.directory(args.application) / 'package.json'),
        'qualification': 'pending runtime review and scoped live acceptance; no primary scores'}
    inputs = {'runtime.json': runtime_path.read_bytes(), 'condition.json': condition_path.read_bytes(),
              'sequence.json': (json.dumps(sequence, indent=2) + '\n').encode(), **requests}
    store = RunStore.create(root, configuration, inputs)
    try:
        if args.evaluator_manifest:
            from .assessment import bind
            bind(store, args.evaluator_manifest)
        return status.build(store)
    except Exception:
        import shutil
        shutil.rmtree(root)
        raise


def derive_evaluation(args):
    """Start a new evaluator ledger from attested completed development evidence."""
    from . import benchmark
    from .assessment import bind
    source = open_run(args, args.source_run)
    target = run_directory(args.runs_root, args.run)
    if target.exists():
        raise ValueError('derived run already exists; use a new run name')
    if source.active_operation()['active']:
        raise ValueError('source run has an active operation; wait before importing')
    source_status = status.build(source)
    for stage, key in (('development', 'runtime_cleanup_required'), ('evaluation', 'evaluation_cleanup_required'),
                       ('reviewer', 'investigation_cleanup_required')):
        if source_status[key]:
            raise ValueError(f'source {stage} runtime cleanup is unresolved')
    package = benchmark.directory(source.configuration['application']) / 'package.json'
    version = json.loads(package.read_text()).get('version')
    if version != source.configuration.get('package_version'):
        raise ValueError('current package version differs from source development; use a compatible release')
    store = RunStore.derive(source, target, run_name=args.run, package_version=version, package_sha256=digest(package))
    try:
        bind(store, args.evaluator_manifest)
        return status.build(store)
    except Exception:
        import shutil
        shutil.rmtree(target)
        raise


def develop(store, args):
    from .development_runtime import DevelopmentRuntime, load_config
    with store.lock('development'):
        require_no_cleanup(status.build(store), 'development')
        step = selected_step(store, args.step)
        pipeline.check_develop(store, step, retry=args.retry)
        load_config(store.root / 'runtime.json')
        runtime = DevelopmentRuntime(store.root / 'runtime.json', store.development, store.root)
        pipeline.develop(store, step, retry=args.retry, runtime=runtime)
    return status.build(store)


def evaluate(store, args):
    from .assessment import RestrictedEvaluator
    with store.lock('independent evaluation'):
        require_no_cleanup(status.build(store), 'evaluation')
        if store.binding is None:
            raise ValueError('evaluator is unbound; bind a qualified package before evaluation')
        step = selected_step(store, args.step)
        evaluator = RestrictedEvaluator(store.binding, store.frozen('runtime.json').get('docker', 'docker'),
                                    root=store.root, search_roots=args.evaluator_root)
        pipeline.evaluate(store, step, rerun=args.rerun, evaluator=evaluator)
    return status.build(store)


def investigate(store, args):
    from .investigation import review_checkpoint
    with store.lock('security investigation'):
        mode = store.configuration.get('investigation', 'none')
        if mode == 'none' or (mode == 'final' and not args.final) or (mode == 'each-step' and args.final):
            raise ValueError('investigation is not enabled for this command in the frozen run')
        step = store.step_ids[-1] if args.final else selected_step(store, args.step)
        report = status.build(store)
        require_no_cleanup(report, 'security investigation')
        checkpoint = next(entry for entry in report['checkpoints'] if entry['id'] == step)
        review_checkpoint(store, checkpoint, mode=mode, config=args.config, prompt=args.prompt,
                          prompt_version=args.prompt_version, rerun=args.rerun)
    return status.build(store)


# Container cleanup command -> (receipt record kind, label, status key, runtime config of a pending entry).
CONTAINER_CLEANUPS = {
    'cleanup': ('runtime-cleanups', 'development', 'runtime_cleanup_required',
                lambda store, entry: store.root / 'runtime.json'),
    'cleanup-investigation': ('investigation-cleanups', 'investigation', 'investigation_cleanup_required',
                              lambda store, entry: Path(entry['allocation']).parent / 'reviewer-runtime.json'),
}


def cleanup(args):
    """Remove a retained development, evaluation or reviewer container for one step."""
    from .development_runtime import cleanup_runtime
    from .evaluation_cleanup import cleanup as cleanup_evaluation
    store = open_run(args)
    step = selected_step(store, args.step)
    with store.lock(args.command.replace('-', ' ')):
        if args.command == 'cleanup-evaluation':
            cleanup_evaluation(store, step)
            return status.build(store)
        kind, label, key, runtime_config = CONTAINER_CLEANUPS[args.command]
        pending = [entry for entry in status.build(store)[key] if entry['step'] == step]
        if not pending:
            raise ValueError(f'no unresolved {label} runtime allocation for selected checkpoint')
        for entry in pending:
            relative = f'{kind}/{uuid.uuid4()}'
            store.add_record(kind, relative + '/cleanup.json')
            cleanup_runtime(entry['allocation'], runtime_config(store, entry), store.root / relative)
    return status.build(store)


def preview(args):
    from . import preview as runtime_preview
    store = open_run(args)
    step = selected_step(store, args.step)
    with store.lock('preview cleanup' if args.stop else 'preview startup'):
        if args.stop:
            selected = [entry for entry in store.records('previews') if entry['step'] == step]
            if not selected:
                raise ValueError('no retained preview for selected checkpoint')
            for entry in reversed(selected):
                runtime_preview.stop(store.root / entry['directory'])
            return status.build(store)
        checkpoint = store.completed(step)
        if checkpoint is None:
            raise ValueError('completed developer checkpoint required for preview')
        if not args.preview_config:
            raise ValueError('--preview-config required to start a preview')
        runtime_preview.load_config(args.preview_config)
        relative = f'previews/{step}/{uuid.uuid4()}'
        directory = store.root / relative
        # Record the allocation before launch so startup failures remain discoverable.
        store.add_record('previews', {'step': step, 'directory': relative, 'artifact': relative + '/preview.json'})
        try:
            runtime_preview.start(str(checkpoint.snapshot), args.preview_config, directory)
        except (OSError, ValueError) as error:
            if not (directory / 'preview.json').exists():
                directory.mkdir(parents=True, exist_ok=True)
                (directory / 'preview.json').write_text(json.dumps({
                    'outcome': 'preview_preflight_error', 'error': str(error), 'resources_removed': True, 'url': None}))
            raise
    return status.build(store)


def show_logs(args):
    store = open_run(args)
    step = selected_step(store, args.step) if args.step else None
    path, offset, inactive_seen = store.root / 'operator-events.jsonl', 0, False
    while True:
        if path.is_file():
            with path.open() as stream:
                stream.seek(offset)
                while line := stream.readline():
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if (step and event.get('step') != step) or (args.stage and event.get('stage') != args.stage):
                        continue
                    if args.format == 'json':
                        print(json.dumps(event, sort_keys=True), flush=True)
                    else:
                        detail = ' '.join(str(event[key]) for key in ('type', 'item_type', 'outcome', 'artifact') if event.get(key))
                        print(f"{event.get('time', 'unknown')} {event.get('stage', 'stage')} "
                              f"{event.get('step') or ''} {event.get('event', 'event')} {detail}".strip(), flush=True)
                offset = stream.tell()
        if not args.follow:
            break
        active = store.active_operation()['active']
        if not active and inactive_seen:
            break
        inactive_seen = not active
        time.sleep(.5)


def compare(args):
    from .comparison import compare_reports
    result = compare_reports([status.build(open_run(args, run)) for run in args.runs])
    print(json.dumps(result, indent=2) if args.format == 'json' else reporting.comparison_csv(result)
          if args.format == 'csv' else reporting.comparison_markdown(result), end='' if args.format != 'json' else '\n')


def parser():
    from .benchmark import applications
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest='command', required=True)
    comparison = sub.add_parser('compare')
    comparison.add_argument('--runs', nargs='+', required=True)
    comparison.add_argument('--runs-root', default=RUNS_ROOT)
    comparison.add_argument('--format', choices=('markdown', 'json', 'csv'), default='markdown')
    commands = {}
    for name in ('init', 'derive-evaluation', 'develop', 'evaluate', 'status', 'preview', 'cleanup',
                 'cleanup-evaluation', 'cleanup-investigation', 'report', 'logs'):
        command = commands[name] = sub.add_parser(name)
        command.add_argument('--run', required=True)
        command.add_argument('--runs-root', default=RUNS_ROOT)
        command.add_argument('--format', choices=('markdown', 'json', 'csv') if name == 'report' else ('markdown', 'json'),
                             default='markdown')
        command.add_argument('--verbose', action='store_true')
    init = commands['init']
    init.add_argument('--application', choices=applications(), required=True)
    init.add_argument('--runtime-config', required=True)
    init.add_argument('--evaluator-manifest', help='qualified hidden evaluator release; required for a full-sequence run')
    init.add_argument('--condition', default='baseline')
    init.add_argument('--investigation', choices=('none', 'final', 'each-step'), default='final')
    init.add_argument('--steps', type=int, help='steps to freeze; default: every qualified step')
    commands['derive-evaluation'].add_argument('--source-run', required=True, help='completed original run in the same runs root')
    commands['derive-evaluation'].add_argument('--evaluator-manifest', required=True, help='qualified replacement evaluator release')
    commands['develop'].add_argument('--step', required=True)
    commands['develop'].add_argument('--retry', action='store_true')
    target = commands['evaluate'].add_mutually_exclusive_group(required=True)
    target.add_argument('--step')
    target.add_argument('--final', action='store_true', help='review the final frozen checkpoint')
    commands['evaluate'].add_argument('--ai-review', action='store_true', help='run the separate Codex security review instead of hidden checks')
    commands['evaluate'].add_argument('--rerun', action='store_true')
    commands['evaluate'].add_argument('--evaluator-root', type=Path, action='append', default=[],
                                      help='extra directory searched by SHA-256 for evaluator files of runs recorded with a host path')
    commands['evaluate'].add_argument('--config', help='separate reviewer configuration; required with --ai-review')
    commands['evaluate'].add_argument('--prompt', help='reviewer prompt; required with --ai-review')
    commands['evaluate'].add_argument('--prompt-version', help='reviewer prompt version; required with --ai-review')
    commands['preview'].add_argument('--step', required=True)
    commands['preview'].add_argument('--preview-config')
    commands['preview'].add_argument('--stop', action='store_true')
    commands['logs'].add_argument('--follow', action='store_true')
    commands['logs'].add_argument('--step')
    commands['logs'].add_argument('--stage', choices=('develop', 'evaluate', 'ai-review'))
    for name in ('cleanup', 'cleanup-evaluation', 'cleanup-investigation'):
        commands[name].add_argument('--step', required=True)
    return root


def run_command(args):
    """Execute one parsed command and return its status report."""
    if args.command in ('develop', 'evaluate'):
        from .progress import Progress
        store = open_run(args)
        review = args.command == 'evaluate' and args.ai_review
        step = store.step_ids[-1] if args.command == 'evaluate' and args.final else selected_step(store, args.step)
        progress = Progress(store.root, 'ai-review' if review else args.command, step, verbose=args.verbose,
                            interval=10 if args.verbose else 30)
        with progress:
            report = (develop if args.command == 'develop' else investigate if review else evaluate)(store, args)
            progress.result_details = reporting.outcome_details(report, args.command, step, ai_review=review)
        return report, step
    handlers = {'init': initialize, 'derive-evaluation': derive_evaluation, 'preview': preview, 'cleanup': cleanup,
                'cleanup-evaluation': cleanup, 'cleanup-investigation': cleanup}
    handler = handlers.get(args.command, lambda args: status.build(open_run(args)))
    return handler(args), None


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    cli = parser()
    args = cli.parse_args()
    if args.command == 'evaluate':
        if args.final and not args.ai_review:
            cli.error('--final requires --ai-review')
        if args.ai_review and not all((args.config, args.prompt, args.prompt_version)):
            cli.error('--ai-review requires --config, --prompt and --prompt-version')
        if not args.ai_review and any((args.config, args.prompt, args.prompt_version)):
            cli.error('reviewer options require --ai-review')
    try:
        if args.command == 'compare':
            return compare(args)
        if args.command == 'logs':
            return show_logs(args)
        report, step = run_command(args)
        if args.command == 'report':
            RunStore(report['root']).save_reports(reporting.files(report))
        print(json.dumps(report, indent=2) if args.format == 'json' else reporting.csv_report(report)
              if args.format == 'csv' else reporting.development_summary(report, step)
              if args.command == 'develop' and not args.verbose else reporting.markdown(report), end='')
    except (OSError, ValueError, KeyError, TypeError) as error:
        cli.error(str(error))


if __name__ == '__main__':
    main()

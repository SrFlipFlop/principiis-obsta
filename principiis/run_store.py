"""Run store: the run directory layout and every controller record in it.

Other modules ask the store for paths and records; they never parse controller
JSON themselves. Layout under `$PRINCIPIIS_RUNS_ROOT/<run>/`:

    configuration.json   freeze manifest: identity, mode, controller commit, and
                         `frozen_files` digests of the frozen inputs below
    sequence.json, requests/, runtime.json, condition.json    frozen inputs
    lineage.json         evaluation-derived runs only
    evaluator-binding.json, evaluator-manifest.json, evaluator-release.json
    development/manual.json                       development attempt journal
    development/steps/<step>/, development/attempts/<step>/<n>/   attempt evidence
    development/evaluations/<step>/allocations.json, <n>/     assessment ledger
    investigation-binding.json, investigations/<step>/<n>/   AI review attempts
    previews/, runtime-cleanups/, evaluation-cleanups/, investigation-cleanups/

`RunStore.open` verifies the freeze manifest, lineage, evaluator binding, journal,
retained snapshots and assessment ledgers once. Writes through the store keep
its in-memory view current, so a command never re-verifies what it just loaded.
Runs written before the store (with a journal fingerprint and `tasks/`) read
unchanged; those extra records are ignored.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

from .benchmark import cumulative_request
from .evaluator_lookup import copy_evaluator, identity
from .jsonio import digest, write_json
from .snapshot import validate

REPOSITORY = Path(__file__).resolve().parents[1]
MAX_ATTEMPTS = 4  # One attempt plus the three explicit retries.


def _nonblank_text(value):
    return isinstance(value, str) and bool(value.strip()) and '\0' not in value


@lru_cache(maxsize=None)
def controller():
    """The controller's git commit; `dirty` when its tracked sources differ from it."""
    def git(*args):
        done = subprocess.run(['git', '-C', str(REPOSITORY), *args], capture_output=True, text=True, timeout=10)
        if done.returncode:
            raise OSError(done.stderr)
        return done.stdout.strip()
    try:
        commit = git('rev-parse', 'HEAD')
        return {'commit': commit, 'dirty': bool(git('status', '--porcelain', '--untracked-files=no', '--', 'principiis'))}
    except (OSError, subprocess.SubprocessError):
        return {'commit': None, 'dirty': None}


def run_directory(runs_root, name):
    """The validated directory for run `name`, outside the research checkout."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name or ''):
        raise ValueError('run must be a single name containing letters, numbers, dots, underscores or hyphens')
    root = Path(runs_root).expanduser().resolve() / name
    if any(value in str(root) for value in (',', '\n', '\r', '\0')):
        raise ValueError('run directory cannot contain commas/newlines or NUL bytes')
    if root.is_relative_to(REPOSITORY) or REPOSITORY.is_relative_to(root):
        raise ValueError('run directory must be outside the research checkout')
    if root.is_symlink():
        raise ValueError('run directory cannot be a symlink')
    for ancestor in (root, *root.parents):
        if any((ancestor / item).exists() for item in ('AGENTS.md', 'AGENTS.override.md')) or any(
                (ancestor / item).is_dir() and any((ancestor / item).iterdir()) for item in ('.agents', '.codex')):
            raise ValueError('run directory has researcher instructions/configuration in its ancestors')
    return root


def attempt_path(step, number):
    return Path('steps') / step if number == 1 else Path('attempts') / step / str(number)


@dataclass
class Attempt:
    """One development allocation; `result` is None until the controller writes it."""
    step: str
    number: int
    directory: Path
    result: dict = None

    @property
    def completed(self):
        return bool(self.result and self.result.get('completed') is True)

    @property
    def snapshot(self):
        return self.directory / 'snapshot'


class RunStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.development = self.root / 'development'

    # ---- creation ---------------------------------------------------------

    @classmethod
    def create(cls, root, configuration, inputs):
        """Write frozen `inputs` ({relative name: bytes}) and the freeze manifest once."""
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=False)
        os.chmod(root, 0o700)
        try:
            for name, content in inputs.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            if (root / 'runtime.json').exists():
                os.chmod(root / 'runtime.json', 0o600)
            frozen = {name: digest(root / name) for name in inputs}
            write_json(root / 'configuration.json', dict(configuration, controller=controller(), frozen_files=frozen))
            return cls.open(root)
        except BaseException:
            shutil.rmtree(root)
            raise

    @classmethod
    def derive(cls, source, root, *, run_name, package_version, package_sha256):
        """A new evaluation-only run holding a verified copy of `source`'s development."""
        root = Path(root).resolve()
        if root.exists():
            raise ValueError('derived run already exists; use a new run name')
        if source.configuration.get('run_mode') == 'evaluation-derived':
            raise ValueError('derive from an original development run, not another evaluation import')
        if [attempt.step for attempt in source.attempts if attempt.completed] != source.step_ids:
            raise ValueError('every source checkpoint must have one completed development result')
        files = source.development_files()
        root.mkdir(parents=True, exist_ok=False)
        os.chmod(root, 0o700)
        try:
            for name in source.configuration['frozen_files']:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source.root / name, root / name)
            (root / 'development').mkdir()
            shutil.copy2(source.development / 'manual.json', root / 'development/manual.json')
            for name in ('tasks', 'steps', 'attempts'):
                if (source.development / name).is_dir():
                    shutil.copytree(source.development / name, root / 'development' / name, symlinks=True)
            if source.development_files() != files or cls(root).development_files() != files:
                raise ValueError('source development changed during import; discard this derived run')
            binding = source.root / 'evaluator-binding.json'
            write_json(root / 'lineage.json', {
                'schema_version': 1, 'source_run': source.configuration['run_name'], 'source_root': str(source.root),
                'source_run_id': source.run_id, 'source_configuration_sha256': digest(source.root / 'configuration.json'),
                'source_binding_sha256': digest(binding) if binding.is_file() else None, 'development_files': files})
            write_json(root / 'configuration.json', dict(
                source.configuration, run_name=run_name, run_mode='evaluation-derived', evaluator_binding='unbound',
                investigation='none', package_version=package_version, package_sha256=package_sha256,
                controller=controller(),
                qualification='evaluation-only import of completed retained development; no model launch',
                source_run={'run_name': source.configuration['run_name'], 'root': str(source.root), 'run_id': source.run_id},
                lineage_sha256=digest(root / 'lineage.json')))
            return cls.open(root)
        except BaseException:
            shutil.rmtree(root)
            raise

    # ---- loading: everything is verified here, once -----------------------

    @classmethod
    def open(cls, root, *, run_name=None):
        store = cls(root)
        store._load(run_name)
        return store

    def _load(self, run_name):
        root = self.root
        self.configuration = json.loads((root / 'configuration.json').read_text())
        if run_name is not None and self.configuration.get('run_name') != run_name:
            raise ValueError('run identity differs from its saved configuration')
        for name, expected in self.configuration['frozen_files'].items():
            path = root / name
            if path.is_symlink() or not path.is_file() or digest(path) != expected:
                raise ValueError('saved development configuration changed; use a new run')
        if self.configuration.get('run_mode') == 'evaluation-derived':
            self._verify_lineage()
        self.sequence = json.loads((root / 'sequence.json').read_text())
        self.step_ids = [step['id'] for step in self.sequence['steps']]
        self.binding = self._load_binding()
        self.run_id, self.attempts = self._load_journal()
        self.assessments = self._load_assessments() if self.binding else []

    def _verify_lineage(self):
        lineage = self.root / 'lineage.json'
        if lineage.is_symlink() or not lineage.is_file() or digest(lineage) != self.configuration.get('lineage_sha256'):
            raise ValueError('evaluation import lineage changed')
        provenance = json.loads(lineage.read_text())
        source = self.root.parent / provenance['source_run']
        binding = source / 'evaluator-binding.json'
        if binding.is_symlink() or (binding.exists() and not binding.is_file()):
            raise ValueError('source development lineage changed')
        if (source.is_symlink() or str(source.resolve()) != provenance['source_root']
                or provenance['source_run'] != self.configuration['source_run']['run_name']
                or provenance['source_root'] != self.configuration['source_run']['root']
                or digest(source / 'configuration.json') != provenance['source_configuration_sha256']
                or (digest(binding) if binding.is_file() else None) != provenance['source_binding_sha256']
                or RunStore(source).development_files() != provenance['development_files']):
            raise ValueError('source development lineage changed')
        if self.development_files() != provenance['development_files']:
            raise ValueError('imported development evidence changed')

    def _load_binding(self):
        path = self.root / 'evaluator-binding.json'
        if not path.exists():
            if (self.development / 'evaluations').exists():
                raise ValueError('retained assessments exist without their evaluator binding')
            return None
        frozen, release = self.root / 'evaluator-manifest.json', self.root / 'evaluator-release.json'
        if path.is_symlink() or frozen.is_symlink() or release.is_symlink():
            raise ValueError('evaluator binding cannot be a symlink')
        binding = json.loads(path.read_text())
        if (digest(frozen) != binding['manifest_sha256'] or digest(release) != binding['package_sha256']
                or json.loads(frozen.read_text()) != binding['declaration']
                or binding['files'] != binding['declaration']['files']
                or binding['version'] != binding['declaration']['version']
                or digest(self.root / 'configuration.json') != binding['development_configuration_sha256']):
            raise ValueError('retained evaluator binding changed')
        return binding

    def _load_journal(self):
        """Canonical controller allocations only; candidate-owned files never count."""
        journal = self.development / 'manual.json'
        if not journal.exists():
            if self.development.exists():
                raise ValueError('development directory exists without its allocation journal')
            return None, []
        state = json.loads(journal.read_text())
        if not isinstance(state, dict) or not _nonblank_text(state.get('run_id')) or not isinstance(state.get('attempts'), list):
            raise ValueError('invalid manual journal')
        counts, completed, sessions, attempts, prior = {}, set(), set(), [], None
        for record in state['attempts']:
            if not isinstance(record, dict):
                raise ValueError('invalid manual journal attempt')
            step, number = record.get('id'), record.get('attempt')
            if (not _nonblank_text(step) or not isinstance(number, int) or isinstance(number, bool)
                    or number != counts.get(step, 0) + 1 or not 1 <= number <= MAX_ATTEMPTS):
                raise ValueError('invalid manual journal attempt identity/order')
            if step not in self.step_ids:
                raise ValueError('unknown checkpoint in manual journal')
            if prior != step:
                index = 0 if prior is None else self.step_ids.index(prior) + 1
                if index >= len(self.step_ids) or step != self.step_ids[index] or (prior is not None and prior not in completed):
                    raise ValueError('out-of-order checkpoint in manual journal')
            elif step in completed:
                raise ValueError('completed checkpoint has an extra attempt in manual journal')
            relative = attempt_path(step, number)
            if record.get('artifact') != str(relative):
                raise ValueError('noncanonical artifact path in manual journal')
            directory = self.development / relative
            if directory.resolve() != directory or (directory / 'result.json').is_symlink():
                raise ValueError('symlinked artifact path in manual journal')
            path = directory / 'result.json'
            result = json.loads(path.read_text()) if path.exists() else None
            if result is None:
                if record.get('completed') is True or (directory / 'snapshot').exists():
                    raise ValueError('completed checkpoint evidence missing from manual journal artifact')
            else:
                if (not isinstance(result, dict) or result.get('run_id') != state['run_id']
                        or result.get('checkpoint') != step or result.get('attempt') != number
                        or not _nonblank_text(result.get('session_id')) or result['session_id'] in sessions):
                    raise ValueError('result identity disagrees with manual journal')
                sessions.add(result['session_id'])
                if record.get('completed') is True and result.get('completed') is not True:
                    raise ValueError('completed checkpoint status disagrees with manual journal')
                if result.get('completed') is True:
                    validate(directory / 'snapshot')
                    completed.add(step)
            counts[step] = number
            prior = step
            attempts.append(Attempt(step, number, directory, result))
        self._journal = state
        return state['run_id'], attempts

    def _load_assessments(self):
        records = []
        for step in self.step_ids:
            parent = self.development / 'evaluations' / step
            ledger = parent / 'allocations.json'
            if not ledger.exists():
                if parent.exists():
                    raise ValueError('assessment directory has no canonical allocation ledger')
                continue
            if parent.resolve() != parent or ledger.is_symlink():
                raise ValueError('assessment ledger cannot be a symlink')
            allocations = json.loads(ledger.read_text())
            if not isinstance(allocations, list):
                raise ValueError('invalid assessment ledger')
            checkpoint = self.completed(step)
            for index, allocation in enumerate(allocations, 1):
                if (not isinstance(allocation, dict) or allocation.get('attempt') != index
                        or allocation.get('checkpoint') != step
                        or allocation.get('role') != ('primary' if index == 1 else 'rerun')
                        or allocation.get('stage') != 'independent_evaluation'
                        or allocation.get('binding_sha256') != self.binding['manifest_sha256']):
                    raise ValueError('invalid canonical assessment allocation')
                path = parent / str(index) / 'result.json'
                if path.resolve() != path:
                    raise ValueError('assessment result cannot be a symlink')
                result = json.loads(path.read_text()) if path.is_file() else dict(
                    allocation, error='controller interrupted after allocation; measurements unavailable')
                for key in ('run_id', 'session_id', 'checkpoint', 'attempt', 'role', 'binding_sha256',
                            'developer_result_sha256', 'snapshot_manifest_sha256'):
                    if result.get(key) != allocation.get(key):
                        raise ValueError('assessment result differs from canonical allocation')
                if (checkpoint is None or result.get('run_id') != self.run_id
                        or result.get('developer_result_sha256') != digest(checkpoint.directory / 'result.json')
                        or result.get('snapshot_manifest_sha256') != digest(checkpoint.directory / 'snapshot.json')
                        or result.get('snapshot') != str(checkpoint.snapshot)):
                    raise ValueError('assessment identity differs from completed development checkpoint')
                records.append(dict(result, artifact=str(path)))
        identities = [result['session_id'] for result in records]
        if len(set(identities)) != len(identities):
            raise ValueError('duplicate assessment session identity')
        return records

    # ---- queries -----------------------------------------------------------

    def attempts_for(self, step):
        return [attempt for attempt in self.attempts if attempt.step == step]

    def completed(self, step):
        """The completed attempt for `step`, or None."""
        return next((attempt for attempt in self.attempts if attempt.step == step and attempt.completed), None)

    def assessments_for(self, step):
        return [assessment for assessment in self.assessments if assessment['checkpoint'] == step]

    def frozen(self, name):
        """A frozen JSON input such as `runtime.json`, verified when the store opened."""
        if name not in self.configuration['frozen_files']:
            raise ValueError('not a frozen run input: ' + name)
        return json.loads((self.root / name).read_text())

    def request_text(self, through):
        """The cumulative request text a developer sees at step index `through` (0-based)."""
        return cumulative_request((self.root / step['request']).read_text() for step in self.sequence['steps'][:through + 1])

    def development_files(self):
        """Inventory of development evidence, excluding later evaluations."""
        paths = [self.development / 'manual.json']
        for name in ('tasks', 'steps', 'attempts'):
            directory = self.development / name
            if directory.is_dir() and not directory.is_symlink():
                paths.extend(path for path in directory.rglob('*') if not path.is_dir() or path.is_symlink())
            elif directory.exists() or directory.is_symlink():
                raise ValueError('imported development evidence has an invalid directory')
        inventory = {}
        for path in paths:
            name = str(path.relative_to(self.root))
            if path.is_symlink():
                inventory[name] = {'symlink': os.readlink(path)}
            elif path.is_file():
                inventory[name] = {'sha256': digest(path)}
            else:
                raise ValueError('imported development evidence is missing: ' + name)
        return inventory

    def records(self, kind):
        """Indexed auxiliary records: previews, runtime and investigation cleanups."""
        index = self.root / kind / 'index.json'
        if index.is_symlink():
            raise ValueError(f'{kind} index cannot be a symlink')
        if not index.is_file():
            return []
        entries = []
        for entry in json.loads(index.read_text()):
            relative = entry['artifact'] if isinstance(entry, dict) else entry
            path = self.root / relative
            if not path.resolve().is_relative_to(self.root / kind):
                raise ValueError(f'{kind} evidence must stay within controller artifacts')
            record = json.loads(path.read_text()) if path.is_file() else None
            entries.append(dict(entry, evidence=record) if isinstance(entry, dict) else
                           record if record is not None else {'outcome': 'interrupted_cleanup'})
        return entries

    def investigations(self):
        found = []
        for step in self.step_ids:
            parent = self.root / 'investigations' / step
            if not parent.is_dir():
                continue
            directories = list(parent.iterdir())
            if any(not d.name.isdigit() or d.is_symlink() or not d.is_dir() for d in directories):
                raise ValueError('invalid investigation allocation directory')
            for directory in sorted(directories, key=lambda d: int(d.name)):
                path = directory / 'investigation.json'
                if path.is_symlink() or not path.resolve().is_relative_to(self.root / 'investigations'):
                    raise ValueError('investigation evidence must stay inside run artifacts')
                record = json.loads(path.read_text()) if path.is_file() else {
                    'status': 'interrupted_allocation', 'claims': [], 'verified_root_causes': [],
                    'resources': {'elapsed_seconds': None, 'reported_tokens': None}}
                found.append(dict(record, checkpoint=step, artifact=str(path)))
        return found

    def investigation_directory(self, step):
        """Where `step`'s next AI review attempt goes; the reviewer creates it."""
        numbers = [int(Path(entry['artifact']).parent.name) for entry in self.investigations()
                   if entry['checkpoint'] == step]
        return self.root / 'investigations' / step / str(max(numbers, default=0) + 1)

    def record(self, path):
        """A retained controller JSON record inside this run, such as an attempt result or a
        container allocation next to its evidence; None when it was never written."""
        path = Path(path)
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError('run record must be a regular file inside the run')
        return json.loads(path.read_text()) if path.is_file() else None

    # ---- writes -----------------------------------------------------------

    def allocate_attempt(self, step):
        """Durably journal the next attempt for `step` before any process starts."""
        number = len(self.attempts_for(step)) + 1
        if self.run_id is None:
            self.development.mkdir(exist_ok=False)
            self.run_id = str(uuid.uuid4())
            self._journal = {'run_id': self.run_id, 'attempts': []}
        relative = attempt_path(step, number)
        self._journal['attempts'].append({'id': step, 'artifact': str(relative), 'attempt': number})
        write_json(self.development / 'manual.json', self._journal)
        attempt = Attempt(step, number, self.development / relative)
        self.attempts.append(attempt)
        return attempt

    def save_attempt(self, attempt, result, *, final=False):
        attempt.directory.mkdir(parents=True, exist_ok=True)
        write_json(attempt.directory / 'result.json', result)
        (attempt.directory / 'report.md').write_text(
            f"Run {result['run_id']}\n\nTask: {result['task']['id']} @ {result['task']['version']}\n\n"
            f"Condition: {result['condition']['id']} @ {result['condition']['version']}\n\n"
            f"Attempt: {result['attempt']}; checkpoint: {result['checkpoint']}\n\n"
            f"Outcome: {result['outcome']}\n\nFunctional: {result['functional']}; security: {result['security']}\n")
        attempt.result = result
        if final:
            entry = self._journal['attempts'][self.attempts.index(attempt)]
            entry.update(completed=result['completed'], outcome=result['outcome'])
            write_json(self.development / 'manual.json', self._journal)

    def allocate_assessment(self, record):
        """Durably ledger an assessment before its runtime starts; returns its directory."""
        parent = self.development / 'evaluations' / record['checkpoint']
        parent.mkdir(parents=True, exist_ok=True)
        ledger = parent / 'allocations.json'
        entries = json.loads(ledger.read_text()) if ledger.exists() else []
        entries.append(record)
        write_json(ledger, entries)
        output = parent / str(record['attempt'])
        output.mkdir(exist_ok=False)
        self.save_assessment(output, record)
        return output

    def save_assessment(self, output, result):
        write_json(output / 'result.json', result)
        artifact = str(output / 'result.json')
        self.assessments = [entry for entry in self.assessments if entry['artifact'] != artifact]
        self.assessments.append(dict(result, artifact=artifact))
        self.assessments.sort(key=lambda entry: (self.step_ids.index(entry['checkpoint']), entry['attempt']))

    def bind(self, binding, declaration, release):
        """Freeze the evaluator declaration and public release next to its binding."""
        binding = dict(binding, development_configuration_sha256=digest(self.root / 'configuration.json'))
        target = self.root / 'evaluator-binding.json'
        if target.is_symlink():
            raise ValueError('evaluator binding cannot be a symlink')
        if target.exists():
            existing = json.loads(target.read_text())
            if identity(existing) != identity(binding):
                raise ValueError('evaluator binding changed; preserve this run and use a new run')
            binding = existing
        else:
            if 'manifest' in binding:
                binding = dict(binding, source_manifest=binding['manifest'],
                               manifest=copy_evaluator(self.root, declaration, binding['files']))
            (self.root / 'evaluator-manifest.json').write_bytes(Path(declaration).read_bytes())
            (self.root / 'evaluator-release.json').write_bytes(Path(release).read_bytes())
            write_json(target, binding)
        self.binding = binding

    def bind_investigation(self, binding):
        """Freeze the AI reviewer configuration on first use; later reviews must match it."""
        path = self.root / 'investigation-binding.json'
        if path.exists() and json.loads(path.read_text()) != binding:
            raise ValueError('investigation configuration changed; use a new run')
        write_json(path, binding)

    def add_record(self, kind, entry):
        """Index an auxiliary record before its work starts."""
        index = self.root / kind / 'index.json'
        index.parent.mkdir(exist_ok=True)
        entries = json.loads(index.read_text()) if index.exists() else []
        entries.append(entry)
        write_json(index, entries)

    def save_reports(self, files):
        directory = self.root / 'reports'
        directory.mkdir(exist_ok=True)
        for name, text in files.items():
            (directory / name).write_text(text)
        return directory

    # ---- operator lock ----------------------------------------------------

    @contextmanager
    def lock(self, name):
        """Serialize mutations while permitting read-only status inspection."""
        with (self.root / '.operation.lock').open('a+') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('another operator action is active for this run; inspect status and wait') from error
            try:
                write_json(self.root / '.operation.json', {'active': True, 'operation': name, 'controller_pid': os.getpid()})
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def active_operation(self):
        path = self.root / '.operation.lock'
        if not path.exists():
            return {'active': False}
        with path.open() as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                try:
                    return dict(json.loads((self.root / '.operation.json').read_text()), active=True)
                except (OSError, ValueError):
                    return {'active': True, 'operation': 'unknown'}
            fcntl.flock(lock, fcntl.LOCK_UN)
        return {'active': False}

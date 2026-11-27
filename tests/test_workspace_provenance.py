"""Development workspaces must not carry research-side Git history (issue #75 item 1d)."""
import io
import json
from pathlib import Path
import unittest

import test_checkpoint_pipeline as pipeline_tests
import test_development_runtime as runtime_tests
from support import temporary_directory
from principiis import pipeline
from principiis.development_runtime import DevelopmentRuntime
from principiis.snapshot import forbid_foreign_git

CASES = {
    'gitfile': lambda w: (w / '.git').write_text('gitdir: /home/someone/research/.git/worktrees/x\n'),
    'nested gitfile': lambda w: ((w / 'sub').mkdir(), (w / 'sub/.git').write_text('gitdir: /elsewhere/.git\n')),
    'alternates': lambda w: ((w / '.git/objects/info').mkdir(parents=True),
                             (w / '.git/objects/info/alternates').write_text('/home/someone/research/.git/objects\n')),
    'commondir': lambda w: ((w / '.git').mkdir(), (w / '.git/commondir').write_text('/home/someone/research/.git\n')),
    'symlinked git': lambda w: (w / '.git').symlink_to('/home/someone/research/.git'),
}


class ForeignGit(unittest.TestCase):
    def test_foreign_git_references_are_rejected(self):
        for label, build in CASES.items():
            with self.subTest(label), temporary_directory() as directory:
                workspace = Path(directory)
                build(workspace)
                with self.assertRaisesRegex(ValueError, 'research-side Git'):
                    forbid_foreign_git(workspace)

    def test_agent_made_self_contained_repository_is_allowed(self):
        with temporary_directory() as directory:
            workspace = Path(directory)
            (workspace / '.git/objects').mkdir(parents=True)
            (workspace / '.git/HEAD').write_text('ref: refs/heads/main\n')
            (workspace / '.git/config').write_text('[core]\n\tbare = false\n')
            forbid_foreign_git(workspace)

    def test_empty_workspace_is_allowed(self):
        with temporary_directory() as directory:
            forbid_foreign_git(directory)


class PipelineRefusesForeignGit(unittest.TestCase):
    def setUp(self):
        directory = temporary_directory()
        self.addCleanup(directory.cleanup)
        self.base = Path(directory.name)
        self.create = lambda *args: pipeline_tests.CheckpointPipeline.create(self, *args)
        self.store = self.create('development-rehearsal')

    def test_prior_snapshot_pointing_at_research_history_is_refused_before_a_new_attempt(self):
        class Poisoned(pipeline_tests.FakeRuntime):
            def execute(self, workspace, request, stdout, stderr):
                (workspace / '.git').write_text('gitdir: /home/someone/research/.git\n')
                return super().execute(workspace, request, stdout, stderr)
        pipeline.develop(self.store, 'step-01', retry=False, runtime=Poisoned())
        runtime = pipeline_tests.FakeRuntime()
        with self.assertRaisesRegex(ValueError, 'research-side Git'):
            pipeline.develop(self.store, 'step-02', retry=False, runtime=runtime)
        self.assertEqual(runtime.requests, [])
        self.assertEqual(self.store.attempts_for('step-02'), [])


class RuntimeRefusesForeignGit(unittest.TestCase):
    def setup_runtime(self, base):
        auth = base / 'auth.json'
        auth.write_text('opaque-test-auth-not-read-by-controller')
        path = base / 'runtime.json'
        path.write_text(json.dumps({'version': '1', 'docker': str(runtime_tests.docker_fixture(base)),
                                    'image': runtime_tests.IMAGE, 'auth_file': str(auth),
                                    'clean_runtime_review': 'fixture review'}))
        output = base / 'run'
        return DevelopmentRuntime(path, output, base / 'tasks'), output / 'workspace'

    def test_execute_refuses_a_foreign_git_workspace_before_any_container_or_auth(self):
        for label, build in CASES.items():
            with self.subTest(label), temporary_directory() as directory:
                base = Path(directory)
                runtime, workspace = self.setup_runtime(base)
                workspace.mkdir(parents=True)
                build(workspace)
                log = base / 'commands.jsonl'
                before = log.read_text().splitlines()
                with self.assertRaisesRegex(ValueError, 'research-side Git'):
                    runtime.execute(workspace, 'request', io.StringIO(), io.StringIO())
                self.assertEqual(log.read_text().splitlines(), before)
                self.assertFalse((workspace.parent / 'runtime.json').exists())

    def test_execute_allows_an_agent_made_repository(self):
        with temporary_directory() as directory:
            runtime, workspace = self.setup_runtime(Path(directory))
            (workspace / '.git/objects').mkdir(parents=True)
            evidence = runtime.execute(workspace, 'request', io.StringIO(), io.StringIO())
            self.assertEqual(evidence['exit_status'], 0)


if __name__ == '__main__':
    unittest.main()

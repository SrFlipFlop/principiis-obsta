import json
import os
from pathlib import Path
import shutil
from support import temporary_directory
import unittest
from unittest.mock import patch

from principiis.snapshot import preserve, validate
from principiis.__main__ import run


IMAGE = 'sha256:' + 'a' * 64
BINDING = {'image': IMAGE, 'symlink_targets': ['/usr/local/bin/python3.12']}


class SnapshotRuntimeLinks(unittest.TestCase):
    def setUp(self):
        self.temporary = temporary_directory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / 'workspace'
        self.bin = self.workspace / '.venv/bin'
        self.bin.mkdir(parents=True)
        (self.workspace / '.venv/pyvenv.cfg').write_text('home = /usr/local/bin\n')
        (self.bin / 'python').symlink_to('/usr/local/bin/python3.12')
        (self.bin / 'python3').symlink_to('python')
        (self.workspace / 'app.py').write_text('print("retained source")\n')
        self.snapshot = self.root / 'snapshot'

    def test_attested_environment_links_round_trip_without_reading_host_targets(self):
        original_read = Path.read_bytes

        def contained_read(path):
            self.assertTrue(path.is_relative_to(self.root), f'host file read: {path}')
            return original_read(path)

        with patch.object(Path, 'read_bytes', contained_read), patch.object(Path, 'resolve', side_effect=AssertionError('must resolve lexically')):
            preserve(self.workspace, self.snapshot, runtime_binding=BINDING)
            validate(self.snapshot, runtime_image=IMAGE)
        manifest = json.loads(self.snapshot.with_suffix('.json').read_text())
        self.assertEqual(manifest['.venv/bin/python'], {'link': '/usr/local/bin/python3.12', 'runtime_image': IMAGE})
        self.assertEqual(manifest['.venv/bin/python3'], {'link': 'python'})
        restored = self.root / 'restored'
        shutil.copytree(self.snapshot, restored, symlinks=True)
        self.assertEqual(os.readlink(restored / '.venv/bin/python'), '/usr/local/bin/python3.12')
        self.assertEqual((restored / 'app.py').read_text(), 'print("retained source")\n')

    def test_runtime_links_require_matching_image_before_consumption(self):
        preserve(self.workspace, self.snapshot, runtime_binding=BINDING)
        validate(self.snapshot)
        for image in (None, 'sha256:' + 'b' * 64):
            with self.subTest(image=image), self.assertRaisesRegex(ValueError, 'runtime image'):
                validate(self.snapshot, runtime_image=image)

    def test_arbitrary_host_link_is_rejected_even_inside_environment(self):
        (self.bin / 'python').unlink()
        (self.bin / 'python').symlink_to('/run/subscription-auth.json')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            preserve(self.workspace, self.snapshot, runtime_binding=BINDING)
        self.assertFalse(self.snapshot.exists())

    def test_symlink_cannot_walk_through_external_interpreter_to_host_directory(self):
        (self.workspace / 'escape').symlink_to('.venv/bin/python/../../etc/passwd')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            preserve(self.workspace, self.snapshot, runtime_binding=BINDING)
        self.assertFalse(self.snapshot.exists())

    def test_internal_directory_alias_to_interpreter_preserves_lexically(self):
        (self.workspace / 'bin').symlink_to('.venv/bin', target_is_directory=True)
        (self.workspace / 'python').symlink_to('bin/python3')
        preserve(self.workspace, self.snapshot, runtime_binding=BINDING)
        validate(self.snapshot, runtime_image=IMAGE)

    def test_relative_escape_and_cycles_remain_rejected(self):
        for target in ('../../secret', 'cycle'):
            with self.subTest(target=target):
                link = self.workspace / 'cycle'
                link.symlink_to(target)
                try:
                    with self.assertRaisesRegex(ValueError, 'symlink'):
                        preserve(self.workspace, self.snapshot, runtime_binding=BINDING)
                finally:
                    link.unlink()

    def test_generic_snapshot_does_not_accept_unattested_runtime_links(self):
        with self.assertRaisesRegex(ValueError, 'symlink'):
            preserve(self.workspace, self.snapshot)
        self.assertFalse(self.snapshot.exists())

    def test_runtime_link_tampering_fails_manifest_verification(self):
        preserve(self.workspace, self.snapshot, runtime_binding=BINDING)
        link = self.snapshot / '.venv/bin/python'
        link.unlink()
        link.symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError, 'snapshot integrity'):
            validate(self.snapshot)

    def test_development_preserves_and_restores_image_bound_environment(self):
        class Runtime:
            snapshot_binding = BINDING

            def execute(adapter, workspace, request, stdout, stderr):
                if request == 'first':
                    shutil.copytree(self.workspace, workspace, dirs_exist_ok=True, symlinks=True)
                else:
                    self.assertEqual(os.readlink(workspace / '.venv/bin/python'), '/usr/local/bin/python3.12')
                    (workspace / 'notes').write_text('continued from retained environment')
                return {'exit_status': 0}

        task = self.root / 'task.json'
        task.write_text(json.dumps({'id': 'one', 'version': '1', 'condition': {'id': 'ordinary', 'version': '1'}}))
        first = self.root / 'first'
        result = run(task, Runtime(), first, visible_request='first', defer_evaluation=True)
        self.assertTrue(result['completed'])
        second = self.root / 'second'
        result = run(task, Runtime(), second, prior_snapshot=first / 'snapshot', visible_request='second', defer_evaluation=True)
        self.assertTrue(result['completed'])
        self.assertEqual((second / 'snapshot/notes').read_text(), 'continued from retained environment')

        class DifferentRuntime(Runtime):
            snapshot_binding = dict(BINDING, image='sha256:' + 'b' * 64)

        rejected = self.root / 'different-image'
        with self.assertRaisesRegex(ValueError, 'runtime image'):
            run(task, DifferentRuntime(), rejected, prior_snapshot=first / 'snapshot', visible_request='second', defer_evaluation=True)
        self.assertFalse(rejected.exists())

    def test_legacy_host_evaluation_cannot_consume_runtime_links(self):
        class Runtime:
            snapshot_binding = BINDING

            def execute(adapter, workspace, request, stdout, stderr):
                shutil.copytree(self.workspace, workspace, dirs_exist_ok=True, symlinks=True)
                return {'exit_status': 0}

        check = self.root / 'check.py'
        marker = self.root / 'host-evaluator-ran'
        check.write_text(f'from pathlib import Path\nPath({str(marker)!r}).touch()\n')
        import sys
        task = self.root / 'task.json'
        task.write_text(json.dumps({'id': 'one', 'version': '1', 'condition': {'id': 'ordinary', 'version': '1'}, 'check': [sys.executable, str(check)]}))
        output = self.root / 'host-evaluation'
        result = run(task, Runtime(), output, visible_request='first')
        self.assertTrue(result['completed'])
        self.assertEqual(result['outcome'], 'evaluator_error')
        self.assertIn('runtime image', result['evaluation']['error'])
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()

"""Progress records are useful without exposing application or evaluator text."""
import json
from pathlib import Path
import tempfile
import unittest

from principiis.progress import Progress, read_events


class ProgressTests(unittest.TestCase):
    def test_partial_codex_line_is_retained_until_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'development/steps/step-01'
            output.mkdir(parents=True)
            log = output / 'executor.stdout'
            with Progress(root, 'develop', 'step-01', interval=10) as progress:
                log.write_text('{"type":"turn.completed"')
                progress.scan()
                self.assertFalse(any(item['event'] == 'codex-event' for item in read_events(root)))
                with log.open('a') as stream:
                    stream.write('}\n')
                progress.scan()
            self.assertEqual(sum(item['event'] == 'codex-event' for item in read_events(root)), 1)

    def test_progress_retains_events_and_exposes_only_event_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'development/steps/step-01'
            output.mkdir(parents=True)
            log = output / 'executor.stdout'
            secret = 'sk-test-should-not-appear'
            with Progress(root, 'develop', 'step-01', verbose=False, interval=0.01) as progress:
                log.write_text(json.dumps({'type': 'item.completed', 'item': {
                    'type': 'agent_message', 'text': secret}}) + '\n')
                progress.scan()
            lines = read_events(root)
            self.assertTrue(any(item['event'] == 'codex-event' for item in lines))
            self.assertNotIn(secret, (root / 'operator-events.jsonl').read_text())
            self.assertEqual(lines[-1]['event'], 'completed')


if __name__ == '__main__':
    unittest.main()

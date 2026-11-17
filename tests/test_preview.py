import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from principiis.preview import start, stop
from principiis.snapshot import preserve, validate
from test_development_runtime import IMAGE, docker_fixture


class PreviewTests(unittest.TestCase):
    def test_runtime_bound_snapshot_rejects_different_preview_image_before_docker(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / 'source'; source.mkdir()
            (source / 'python').symlink_to('/usr/local/bin/python3.12')
            snapshot = base / 'snapshot'
            preserve(source, snapshot, runtime_binding={
                'image': IMAGE, 'symlink_targets': ['/usr/local/bin/python3.12']})
            docker = docker_fixture(base)
            config = base / 'config'
            config.write_text(json.dumps({'version': '1', 'docker': str(docker), 'preview': {
                'image': 'sha256:' + 'b' * 64, 'command': ['./python', 'app.py'],
                'container_port': 8123, 'host_port': 0, 'ready_path': '/ready',
                'startup_timeout_seconds': 1}}))
            with self.assertRaisesRegex(ValueError, 'runtime|image'):
                start(snapshot, config, base / 'preview')
            self.assertFalse((base / 'preview').exists())
            self.assertFalse((base / 'commands.jsonl').exists())

    def test_restricted_preview_uses_copy_loopback_and_explicit_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with patch('principiis.preview.http.client.HTTPConnection') as connection:
                connection.return_value.getresponse.return_value.status = 200
                docker = docker_fixture(base)
                source = base/'source'; source.mkdir(); (source/'app.py').write_text('candidate bytes')
                snapshot = base/'snapshot'; preserve(source,snapshot)
                config = base/'preview-config.json'
                config.write_text(json.dumps({'version':'1','docker':str(docker),'preview':{
                    'image':IMAGE,'command':['python','app.py'],'container_port':8123,
                    'host_port':0,'ready_path':'/ready','startup_timeout_seconds':2}}))
                output = base/'preview'
                record = start(snapshot,config,output)
                self.assertEqual(record['outcome'],'ready')
                self.assertEqual(record['url'],'http://127.0.0.1:58123')
                connection.assert_called_once_with('127.0.0.1',58123,timeout=1)
                connection.return_value.request.assert_called_once_with('GET','/ready')
                validate(snapshot)
                self.assertEqual((output/'workspace/app.py').read_text(),'candidate bytes')
                commands = [json.loads(line) for line in (base/'commands.jsonl').read_text().splitlines()]
                network = next(c for c in commands if c[:2] == ['network','create'])
                self.assertIn('--internal', network)
                self.assertIn('com.docker.network.bridge.gateway_mode_ipv4=isolated',network)
                launches = [c for c in commands if c[0] == 'run' and '--detach' in c]
                self.assertEqual(len(launches),2)
                launch, relay = launches
                self.assertNotIn('--publish',launch)
                self.assertIn('127.0.0.1::8123',relay)
                self.assertEqual(relay[relay.index('--network')+1],'bridge')
                self.assertNotIn('--mount',relay)
                self.assertIn('-I',relay)
                self.assertIn('-S',relay)
                self.assertIn('net.ipv4.ip_forward=0',relay)
                self.assertEqual(record['relay_target'],{'host':'172.30.0.2','port':8123})
                self.assertTrue(any(c[:2]==['network','connect'] and c[-1]==record['relay_container'] for c in commands))
                mounts = [launch[i+1] for i,v in enumerate(launch) if v == '--mount']
                self.assertEqual(mounts,[f'type=bind,src={output}/workspace,dst=/workspace'])
                self.assertNotIn(str(snapshot),repr(launch))
                self.assertIn('--read-only',launch)
                stopped = stop(output)
                self.assertEqual(stopped['outcome'],'stopped')
                self.assertIn('application startup', '\n'.join(p.read_text() for p in output.glob('*.stdout')))
                self.assertEqual(stop(output)['outcome'],'stopped')
                validate(snapshot)
                after=[json.loads(line) for line in (base/'commands.jsonl').read_text().splitlines()]
                removals=[c for c in after if c[:2]==['rm','-f']]
                self.assertEqual([c[-1] for c in removals],[record['relay_container'],record['container']])

    def test_tampered_snapshot_rejected_without_allocating_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base/'source'; source.mkdir(); (source/'app.py').write_text('original')
            snapshot = base/'snapshot'; preserve(source,snapshot)
            (snapshot/'app.py').write_text('tampered')
            docker = docker_fixture(base)
            config = base/'config'; config.write_text(json.dumps({'version':'1','docker':str(docker),'preview':{
                'image':IMAGE,'command':['python','app.py'],'container_port':8123,
                'host_port':0,'ready_path':'/ready','startup_timeout_seconds':1}}))
            with self.assertRaisesRegex(ValueError,'snapshot integrity'):
                start(snapshot,config,base/'preview')
            self.assertFalse((base/'preview').exists())
            self.assertFalse((base/'commands.jsonl').exists())

    def test_failed_start_retains_evidence_and_cleans_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            docker=docker_fixture(base)
            docker.write_text(docker.read_text().replace("'Running':True", "'Running':False"))
            source=base/'source';source.mkdir();(source/'app.py').write_text('broken candidate')
            snapshot=base/'snapshot';preserve(source,snapshot)
            config=base/'config';config.write_text(json.dumps({'version':'1','docker':str(docker),'preview':{
                'image':IMAGE,'command':['python','app.py'],'container_port':8123,
                'host_port':0,'ready_path':'/ready','startup_timeout_seconds':1}}))
            record=start(snapshot,config,base/'preview')
            self.assertEqual(record['outcome'],'preview_error')
            self.assertIn('exited',record['error'])
            self.assertTrue((base/'preview/preview.json').exists())
            self.assertTrue((base/'preview/workspace/app.py').exists())
            commands=[json.loads(line) for line in (base/'commands.jsonl').read_text().splitlines()]
            self.assertTrue(any(c[:2]==['rm','-f'] for c in commands))
            self.assertTrue(any(c[:2]==['network','rm'] for c in commands))
            validate(snapshot)

    def test_null_relay_binding_is_a_retained_error_and_cleans_both_containers(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            docker=docker_fixture(base)
            docker.write_text(docker.read_text().replace("'Ports':ports", "'Ports':{'8123/tcp':None}"))
            source=base/'source';source.mkdir();(source/'app.py').write_text('candidate')
            snapshot=base/'snapshot';preserve(source,snapshot)
            config=base/'config';config.write_text(json.dumps({'version':'1','docker':str(docker),'preview':{
                'image':IMAGE,'command':['python','app.py'],'container_port':8123,
                'host_port':0,'ready_path':'/ready','startup_timeout_seconds':1}}))
            record=start(snapshot,config,base/'preview')
            self.assertEqual(record['outcome'],'preview_error')
            self.assertIn('loopback',record['error'])
            commands=[json.loads(line) for line in (base/'commands.jsonl').read_text().splitlines()]
            removals=[c[-1] for c in commands if c[:2]==['rm','-f']]
            self.assertEqual(removals,[record['relay_container'],record['container']])
            self.assertTrue(record['resources_removed'])
            validate(snapshot)

    def test_plain_internal_network_is_rejected_before_candidate_start(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            docker=docker_fixture(base)
            docker.write_text(docker.read_text().replace("gateway_mode_ipv4':'isolated'", "gateway_mode_ipv4':'nat'"))
            source=base/'source';source.mkdir();(source/'app.py').write_text('candidate')
            snapshot=base/'snapshot';preserve(source,snapshot)
            config=base/'config';config.write_text(json.dumps({'version':'1','docker':str(docker),'preview':{
                'image':IMAGE,'command':['python','app.py'],'container_port':8123,
                'host_port':0,'ready_path':'/ready','startup_timeout_seconds':1}}))
            record=start(snapshot,config,base/'preview')
            self.assertEqual(record['outcome'],'preview_error')
            self.assertIn('isolated',record['error'])
            commands=[json.loads(line) for line in (base/'commands.jsonl').read_text().splitlines()]
            self.assertFalse(any(c[0]=='run' for c in commands))
            self.assertTrue(record['resources_removed'])
            validate(snapshot)

"""Opt-in model-free HTTP control; never portal or browser acceptance evidence."""
import http.client
import json
import os
from pathlib import Path
import shutil
from support import temporary_directory
import unittest
import uuid

from principiis.development_runtime import DevelopmentRuntime, docker_run, restrictions
from principiis.preview import start, stop
from principiis.snapshot import preserve, validate


@unittest.skipUnless(os.environ.get('PO_PREVIEW_IMAGE') and os.environ.get('PO_PREVIEW_ROOT'),
                     'requires prepared local Docker preview image and evidence root')
class PreviewContainerQualification(unittest.TestCase):
    def test_reachable_http_control_preserves_source_and_restricted_network(self):
        base = Path(os.environ['PO_PREVIEW_ROOT']).resolve() / ('http-control-' + uuid.uuid4().hex)
        base.mkdir(parents=True)
        source = base / 'source'
        source.mkdir()
        (source / 'app.py').write_text('''from http.server import BaseHTTPRequestHandler, HTTPServer
class Control(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"engineering HTTP control, never a generated portal")
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Set-Cookie", "control=retained; HttpOnly")
        self.end_headers()
        self.wfile.write(body)
HTTPServer(("0.0.0.0", 8123), Control).serve_forever()
''')
        snapshot = base / 'snapshot'
        preserve(source, snapshot)
        docker = os.environ.get('PO_PREVIEW_DOCKER', '/snap/bin/docker')
        image = os.environ['PO_PREVIEW_IMAGE']
        config = base / 'config.json'
        config.write_text(json.dumps({'version': '1', 'docker': docker, 'preview': {
            'image': image, 'command': ['python', 'app.py'], 'container_port': 8123,
            'host_port': 0, 'ready_path': '/ready', 'startup_timeout_seconds': 15,
        }}))
        output = base / 'preview'
        summary = {'scope': 'model-free HTTP control; no generated application or browser qualification',
                   'outcome': 'error', 'evidence': str(base)}
        try:
            record = start(snapshot, config, output)
            self.assertEqual(record['outcome'], 'ready', record.get('error'))
            app = json.loads(docker_run(docker, ['inspect', record['container']]))[0]
            relay = json.loads(docker_run(docker, ['inspect', record['relay_container']]))[0]
            network = json.loads(docker_run(docker, ['network', 'inspect', record['network']]))[0]
            (base / 'effective-isolation.json').write_text(json.dumps({'app': app, 'relay': relay, 'network': network}, indent=2))
            self.assertTrue(network['Internal'])
            self.assertEqual(network['Options']['com.docker.network.bridge.gateway_mode_ipv4'], 'isolated')
            self.assertEqual(app['NetworkSettings']['Networks'][record['network']]['Gateway'], '')
            self.assertFalse(any(app['NetworkSettings']['Ports'].values()))
            self.assertEqual(len(app['Mounts']), 1)
            self.assertEqual(app['Mounts'][0]['Destination'], '/workspace')
            self.assertEqual(relay['Mounts'], [])
            for container in (app, relay):
                self.assertEqual(container['Image'], image)
                self.assertNotEqual(container['Config']['User'].split(':')[0], '0')
                self.assertTrue(container['HostConfig']['ReadonlyRootfs'])
                self.assertFalse(container['HostConfig']['Privileged'])
                self.assertIn('ALL', container['HostConfig']['CapDrop'])
                self.assertTrue(any(value.startswith('no-new-privileges') for value in container['HostConfig']['SecurityOpt']))
            bindings = relay['NetworkSettings']['Ports']['8123/tcp']
            self.assertEqual(len(bindings), 1)
            self.assertEqual(bindings[0]['HostIp'], '127.0.0.1')
            connection = http.client.HTTPConnection('127.0.0.1', int(bindings[0]['HostPort']), timeout=5)
            try:
                payload = b'ordinary form/upload bytes\x00\xff'
                connection.request('POST', '/echo', body=payload)
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), payload)
                self.assertEqual(response.getheader('Set-Cookie'), 'control=retained; HttpOnly')
            finally:
                connection.close()
            validate(snapshot)
            summary['outcome'] = 'pass'
        except BaseException as error:
            summary['error'] = str(error)
            raise
        finally:
            if (output / 'preview.json').is_file():
                cleanup = stop(output)
                summary['cleanup'] = cleanup['outcome']
                summary['resources_removed'] = cleanup['resources_removed']
            (base / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        self.assertTrue(summary['resources_removed'])


@unittest.skipUnless(os.environ.get('PO_RUNTIME_IMAGE') and os.environ.get('PO_PREVIEW_ROOT'),
                     'requires prepared local development image and preview evidence root')
class VirtualEnvironmentPreviewQualification(unittest.TestCase):
    def test_retained_virtual_environment_runs_in_same_image_preview(self):
        base = Path(os.environ['PO_PREVIEW_ROOT']).resolve() / ('venv-control-' + uuid.uuid4().hex)
        base.mkdir(parents=True)
        source = base / 'source'; source.mkdir()
        image = os.environ['PO_RUNTIME_IMAGE']
        docker = os.environ.get('PO_PREVIEW_DOCKER', '/snap/bin/docker')
        auth = base / 'not-credentials.fixture'
        auth.write_text('model-free control; this file is never mounted')
        runtime_config = base / 'runtime.json'
        runtime_config.write_text(json.dumps({'version': '1', 'docker': docker, 'image': image,
            'auth_file': str(auth), 'clean_runtime_review': 'model-free virtual environment control only'}))
        summary = {'scope': 'model-free retained virtual environment and restricted HTTP control',
                   'image': image, 'outcome': 'error', 'evidence': str(base)}
        output = base / 'preview'
        try:
            with temporary_directory(prefix='po-venv-preflight-') as temporary:
                runtime = DevelopmentRuntime(runtime_config, Path(temporary) / 'output', Path(temporary) / 'tasks')
            summary['runtime_version'] = runtime.version
            preparation_name = 'po-venv-preparation-' + uuid.uuid4().hex
            summary['preparation_container'] = preparation_name
            summary['preparation_argv'] = ['run', '--name', preparation_name, '--network', 'none',
                *restrictions(), '--mount', f'type=bind,src={source},dst=/workspace',
                '--entrypoint', 'python', image, '-m', 'venv', '.venv']
            (base / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
            try:
                preparation = docker_run(docker, summary['preparation_argv'], timeout=60)
            finally:
                try:
                    docker_run(docker, ['rm', '-f', preparation_name])
                    summary['preparation_cleanup'] = 'removed'
                except Exception as error:
                    summary['preparation_cleanup_error'] = str(error)
                    raise
            (base / 'preparation.stdout').write_text(preparation)
            (source / 'app.py').write_text('''from http.server import BaseHTTPRequestHandler, HTTPServer
import sys
assert sys.prefix == "/workspace/.venv", sys.prefix
class Control(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"retained virtual environment control")
HTTPServer(("0.0.0.0", 8123), Control).serve_forever()
''')
            snapshot = base / 'snapshot'
            preserve(source, snapshot, runtime_binding=runtime.snapshot_binding)
            manifest_before = snapshot.with_suffix('.json').read_bytes()
            restored = base / 'restored'
            shutil.copytree(snapshot, restored, symlinks=True)
            self.assertEqual(os.readlink(restored / '.venv/bin/python'),
                             os.readlink(source / '.venv/bin/python'))
            config = base / 'preview-config.json'
            config.write_text(json.dumps({'version': '1', 'docker': docker, 'preview': {
                'image': image, 'command': ['.venv/bin/python', 'app.py'], 'container_port': 8123,
                'host_port': 0, 'ready_path': '/ready', 'startup_timeout_seconds': 15}}))
            record = start(snapshot, config, output)
            self.assertEqual(record['outcome'], 'ready', record.get('error'))
            connection = http.client.HTTPConnection(record['url'].split('//')[1], timeout=5)
            try:
                connection.request('GET', '/ready')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b'retained virtual environment control')
            finally:
                connection.close()
            validate(snapshot, runtime_image=image)
            self.assertEqual(snapshot.with_suffix('.json').read_bytes(), manifest_before)
            summary['outcome'] = 'pass'
        except BaseException as error:
            summary['error'] = str(error)
            raise
        finally:
            if (output / 'preview.json').is_file():
                cleanup = stop(output)
                summary['cleanup'] = cleanup['outcome']
                summary['resources_removed'] = cleanup['resources_removed']
            (base / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        self.assertTrue(summary['resources_removed'])

"""Opt-in, no-model/no-auth qualification of the actual development sandbox."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid

from principiis.development_runtime import (DevelopmentRuntime, SANDBOX_PROBE,
    configuration_args, docker_command, docker_run, restrictions, runtime_user, workspace_permission_settings)


@unittest.skipUnless(os.environ.get('PO_RUNTIME_IMAGE') and os.environ.get('PO_RUNTIME_ROOT'),
                     'set PO_RUNTIME_IMAGE and PO_RUNTIME_ROOT for model-free Docker qualification')
class DevelopmentRuntimeContainerTests(unittest.TestCase):
    def test_workspace_sandbox_tools_network_and_effective_container_policy(self):
        image=os.environ['PO_RUNTIME_IMAGE']
        docker=os.environ.get('PO_DOCKER','/snap/bin/docker')
        output=Path(os.environ['PO_RUNTIME_ROOT']).resolve()/('sandbox-control-'+uuid.uuid4().hex)
        output.mkdir(parents=True)
        workspace=output/'workspace';workspace.mkdir()
        auth=output/'not-authentication.fixture';auth.write_text('never mounted by this control')
        config=output/'runtime-config.json'
        config.write_text(json.dumps({'version':'1','docker':docker,'image':image,
            'auth_file':str(auth),'clean_runtime_review':'trusted no-model qualification only'}))
        name='po-development-'+uuid.uuid4().hex
        summary={'scope':'trusted model-free control; no credentials mounted or model calls',
                 'started_at':time.time(),'container':name,'image':image,'outcome':'failed'}
        allocation=output/'summary.json'
        calls=[]
        def call(args,timeout=60):
            calls.append(docker_command(docker,args))
            allocation.write_text(json.dumps(dict(summary,argv=calls),indent=2)+'\n')
            try:
                data=docker_run(docker,args,timeout=timeout)
            except Exception as error:
                (output/f'{len(calls):02d}.stderr').write_text(str(error)+'\n')
                raise
            (output/f'{len(calls):02d}.stdout').write_text(data)
            return data
        try:
            with tempfile.TemporaryDirectory() as directory:
                runtime=DevelopmentRuntime(config,Path(directory)/'output',Path(directory)/'source')
            summary['runtime_version']=runtime.version
            call(['run','--detach','--name',name,'--network','bridge',*restrictions(nested_sandbox=True),
                '--tmpfs','/outside-workspace:rw,nosuid,nodev,size=1m,mode=1777',
                '--mount',f'type=bind,src={workspace},dst=/workspace',
                '--entrypoint','/bin/sh',image,'-c','exec sleep 120'])
            record=json.loads(call(['inspect',name]))[0]
            (output/'container-inspect.json').write_text(json.dumps(record,indent=2)+'\n')
            host=record['HostConfig']
            self.assertFalse(host['Privileged'])
            self.assertTrue(host['ReadonlyRootfs'])
            self.assertEqual(host['CapDrop'],['ALL'])
            self.assertFalse(host.get('CapAdd'))
            self.assertEqual(record['Config']['User'],runtime_user())
            self.assertEqual(host['NetworkMode'],'bridge')
            self.assertIn('no-new-privileges',host['SecurityOpt'])
            self.assertTrue(any(v.startswith('seccomp=') for v in host['SecurityOpt']))
            for mount in ('/tmp', '/home/developer'):
                flags = host['Tmpfs'][mount].split(',')
                self.assertIn('exec', flags)
                self.assertIn('nosuid', flags)
                self.assertIn('nodev', flags)
            binds=[m for m in record['Mounts'] if m['Type']=='bind']
            self.assertEqual([(m['Source'],m['Destination']) for m in binds],[(str(workspace),'/workspace')])
            self.assertTrue(all(m['Destination']!='/run/subscription-auth.json' for m in record['Mounts']))
            # Exercise normal user-local tools in the outer container without
            # changing the inner workspace profile's home-directory write policy.
            call(['exec', name, 'python', '-c', '''import pathlib, subprocess
tool = pathlib.Path.home() / '.local/bin/po-tool-control'
tool.parent.mkdir(parents=True)
tool.write_text('#!/bin/sh\\nexit 0\\n')
tool.chmod(0o700)
subprocess.run([str(tool)], check=True)
print('user-local tool execution: passed')
'''])
            probe=SANDBOX_PROBE+'''\nimport socket
status=pathlib.Path('/proc/self/status').read_text()
assert 'CapEff:\\t0000000000000000' in status
with socket.socket() as listener:
    listener.bind(('127.0.0.1',0)); listener.listen(1)
    with socket.create_connection(listener.getsockname(),timeout=2) as client:
        server,_=listener.accept()
        with server:
            client.sendall(b'network-control')
            assert server.recv(64)==b'network-control'
print('network-enabled-workspace-sandbox: passed')
'''
            result=call(['exec',name,'/bin/sh','-eu','-c',
                'mkdir -p "$CODEX_HOME"; touch /outside-workspace/outer-write; rm /outside-workspace/outer-write; exec "$@"',
                '--','codex','--no-daemon','sandbox','--permission-profile','development',
                *configuration_args(workspace_permission_settings()),'--cd','/workspace','--','python','-c',probe])
            self.assertIn('network-enabled-workspace-sandbox: passed',result)
            self.assertEqual((workspace/'probe.txt').read_text(),'workspace-write')
            self.assertEqual((workspace/'node-probe.txt').read_text(),'ok')
            summary['outcome']='passed'
        except BaseException as error:
            summary['error']=str(error)
            raise
        finally:
            try:
                call(['rm','-f',name],timeout=20)
                summary['cleanup']='removed'
            except Exception as error:
                summary['cleanup_error']=str(error)
                raise
            finally:
                summary.update(finished_at=time.time(),argv=calls)
                allocation.write_text(json.dumps(summary,indent=2)+'\n')
                print('Development sandbox evidence:',output)


if __name__=='__main__':
    unittest.main()

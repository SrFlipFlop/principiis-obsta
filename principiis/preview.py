"""Disposable loopback preview of a verified checkpoint; no host application execution."""
import hashlib
import http.client
import ipaddress
import json
from pathlib import Path
import shutil
import subprocess
import re
import time
import uuid

from .development_runtime import IMAGE_ID, docker_command, docker_environment, inspect_image, local_path, restrictions
from .codex import redact
from .resume import write_json
from .snapshot import validate


# Trusted bytes-only relay: every accepted connection has exactly one fixed target.
# No application files, protocols, request destinations or credentials are interpreted.
RELAY_SCRIPT = '''import select,socket,socketserver,sys
target=(sys.argv[1],int(sys.argv[2]))
class Relay(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            with socket.create_connection(target,timeout=5) as upstream:
                self.request.settimeout(5)
                streams=(self.request,upstream)
                while True:
                    readable,_,_=select.select(streams,[],[],30)
                    if not readable: return
                    for stream in readable:
                        data=stream.recv(65536)
                        if not data: return
                        (upstream if stream is self.request else self.request).sendall(data)
        except OSError:
            return
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address=True
    daemon_threads=True
with Server(('0.0.0.0',int(sys.argv[3])),Relay) as server:
    server.serve_forever()
'''


def load_config(path):
    config = json.loads(Path(path).read_text())
    if not isinstance(config, dict) or set(config) != {'version','docker','preview'} or config.get('version') != '1':
        raise ValueError('preview requires version 1, docker and preview configuration')
    config['docker'] = local_path(config['docker'], 'docker', executable=True)
    p = config['preview']
    keys = {'image','command','container_port','host_port','ready_path','startup_timeout_seconds'}
    if not isinstance(p, dict) or set(p) != keys:
        raise ValueError('preview requires image/command/container_port/host_port/ready_path/startup_timeout_seconds')
    if not isinstance(p['image'], str) or not IMAGE_ID.fullmatch(p['image']):
        raise ValueError('preview image must be pinned by a full local sha256 image ID')
    if not isinstance(p['command'], list) or not p['command'] or any(not isinstance(a,str) or not a or '\x00' in a for a in p['command']):
        raise ValueError('preview command must be a nonempty argv list')
    for field, minimum in (('container_port',1),('host_port',0)):
        if type(p[field]) is not int or not minimum <= p[field] <= 65535:
            raise ValueError('invalid preview port')
    if (not isinstance(p['ready_path'], str) or not p['ready_path'].startswith('/')
            or any(v in p['ready_path'] for v in ('\n','\r','#'))):
        raise ValueError('preview ready_path must be a local absolute HTTP path')
    if type(p['startup_timeout_seconds']) not in (float,int) or not 0 < p['startup_timeout_seconds'] <= 60:
        raise ValueError('preview startup timeout must be greater than 0 and at most 60 seconds')
    return config


def command(record, output, args, *, timeout=20, allow_absent=False):
    argv = docker_command(record['config']['docker'], args)
    record['commands'].append(argv)
    index = len(record['commands'])
    # Save before each operation so an interrupted preview can be explicitly cleaned.
    write_json(output/'preview.json', record)
    try:
        result = subprocess.run(argv, capture_output=True, text=True, env=docker_environment(), timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        (output/f'{index}.stderr').write_text(str(error))
        raise ValueError(f'preview Docker {args[0]} could not complete') from error
    (output/f'{index}.stdout').write_text(redact(result.stdout))
    (output/f'{index}.stderr').write_text(redact(result.stderr))
    if result.returncode:
        if allow_absent:
            name = re.escape(args[-1])
            missing = (rf'(?:Error response from daemon: )?No such container: {name}' if args[0] == 'rm'
                       else rf'(?:Error response from daemon: )?(?:No such network: {name}|network {name} not found)')
            if re.fullmatch(missing,result.stderr.strip()):
                record.setdefault('already_absent',[]).append(args[-1])
                return result.stdout
        raise ValueError(f'preview Docker {args[0]} failed; see {index}.stderr')
    return result.stdout


def cleanup(record, output):
    errors = []
    # Logs are supplementary; failure to fetch them must not skip cleanup.
    containers = ([record['relay_container']] if record.get('relay_launch_attempted') else [])
    if record.get('application_launch_attempted',True):
        containers.append(record['container'])
    for name in containers:
        try:
            command(record,output,['logs',name])
        except ValueError as error:
            record.setdefault('log_errors',[]).append(str(error))
    removals = [['rm','-f',name] for name in containers]
    if record.get('network_create_attempted',True):
        removals.append(['network','rm',record['network']])
    for args in removals:
        try:
            command(record,output,args,allow_absent=True)
        except ValueError as error:
            errors.append(str(error))
    record['cleanup_errors'] = errors
    record['resources_removed'] = not errors


def start(snapshot, config_path, output):
    snapshot, output = Path(snapshot).resolve(), Path(output).resolve()
    config = load_config(config_path)
    validate(snapshot, runtime_image=config['preview']['image'])
    if output.is_relative_to(snapshot) or snapshot.is_relative_to(output):
        raise ValueError('preview output must be separate from retained source')
    if any(v in str(output) for v in (',','\n','\r')):
        raise ValueError('preview output path cannot contain commas/newlines')
    image = inspect_image(config['docker'],config['preview']['image'])
    output.mkdir(parents=True,exist_ok=False)
    output = output.resolve()
    record = {'schema_version':1,'preview_id':str(uuid.uuid4()),'outcome':'starting',
              'snapshot':str(snapshot),'snapshot_manifest_sha256':hashlib.sha256(snapshot.with_suffix('.json').read_bytes()).hexdigest(),
              'config':config,'image':image,'container':'po-preview-'+uuid.uuid4().hex,
              'relay_container':'po-preview-relay-'+uuid.uuid4().hex,
              'relay_script_sha256':hashlib.sha256(RELAY_SCRIPT.encode()).hexdigest(),
              'application_launch_attempted':False,'relay_launch_attempted':False,'network_create_attempted':False,
              'network':'po-preview-'+uuid.uuid4().hex,'commands':[],'url':None,
              'resources_removed':False,'started_at':time.time(),'ready':False}
    write_json(output/'preview.json',record)
    try:
        shutil.copytree(snapshot,output/'workspace',symlinks=True)
        p = config['preview']
        record['network_create_attempted'] = True
        command(record,output,['network','create','--driver','bridge','--internal','--ipv6=false',
                '--opt','com.docker.network.bridge.gateway_mode_ipv4=isolated',record['network']])
        network = json.loads(command(record,output,['network','inspect',record['network']]))[0]
        record['network_inspect'] = network
        if (network.get('Internal') is not True or network.get('EnableIPv6') is not False
                or (network.get('Options') or {}).get('com.docker.network.bridge.gateway_mode_ipv4') != 'isolated'):
            raise ValueError('preview network is not an isolated IPv4 internal bridge')
        port = f'127.0.0.1:{p["host_port"] or ""}:{p["container_port"]}'
        record['application_launch_attempted'] = True
        command(record,output,['run','--detach','--name',record['container'],'--network',record['network'],
                *restrictions(),
                '--env','PORTAL_DATA_DIR=/workspace/data',
                '--mount',f'type=bind,src={output}/workspace,dst=/workspace',
                '--entrypoint',p['command'][0],p['image'],*p['command'][1:]])
        status = json.loads(command(record,output,['inspect',record['container']]))[0]
        record['application_inspect'] = status
        if not status['State']['Running']:
            raise ValueError('preview application exited during startup')
        app_networks = status['NetworkSettings']['Networks']
        if set(app_networks) != {record['network']} or any((status['NetworkSettings'].get('Ports') or {}).values()):
            raise ValueError('preview application must have only its isolated network and no published ports')
        target = ipaddress.ip_address(app_networks[record['network']]['IPAddress'])
        if target.version != 4 or target.is_unspecified or target.is_loopback or target.is_multicast:
            raise ValueError('preview application has an invalid internal IPv4 address')
        record['relay_target'] = {'host':str(target),'port':p['container_port']}
        record['relay_launch_attempted'] = True
        command(record,output,['run','--detach','--name',record['relay_container'],'--network','bridge',
                *restrictions(), '--publish',port,'--sysctl','net.ipv4.ip_forward=0',
                '--entrypoint','python',p['image'],'-I','-S','-u','-c',RELAY_SCRIPT,
                str(target),str(p['container_port']),str(p['container_port'])])
        command(record,output,['network','connect',record['network'],record['relay_container']])
        relay = json.loads(command(record,output,['inspect',record['relay_container']]))[0]
        record['relay_inspect'] = relay
        if not relay['State']['Running']:
            raise ValueError('preview relay exited during startup')
        bindings = (relay['NetworkSettings'].get('Ports') or {}).get(str(p['container_port'])+'/tcp')
        if not isinstance(bindings,list) or len(bindings) != 1 or bindings[0]['HostIp'] != '127.0.0.1':
            raise ValueError('preview port was not bound exclusively to loopback')
        assigned = int(bindings[0]['HostPort'])
        if not 1 <= assigned <= 65535:
            raise ValueError('invalid assigned preview port')
        record['url'] = f'http://127.0.0.1:{assigned}'
        deadline = time.monotonic() + p['startup_timeout_seconds']
        while time.monotonic() < deadline:
            connection = http.client.HTTPConnection('127.0.0.1',assigned,timeout=min(1,p['startup_timeout_seconds']))
            try:
                connection.request('GET',p['ready_path'])
                status_code = connection.getresponse().status
                record['ready_http_status'] = status_code
                if status_code == 200:
                    record.update(outcome='ready',ready=True)
                    break
            except (OSError,http.client.HTTPException) as error:
                record['readiness_error'] = str(error)
            finally:
                connection.close()
            time.sleep(.1)
        if not record['ready']:
            raise ValueError('preview readiness probe did not return HTTP 200 before startup timeout')
        for name in (record['container'],record['relay_container']):
            command(record,output,['logs',name])
        validate(snapshot, runtime_image=config['preview']['image'])
    except (OSError,ValueError,KeyError,TypeError,IndexError,KeyboardInterrupt) as error:
        record.update(outcome='preview_error',error=str(error) or 'preview interrupted',ready=False)
        cleanup(record,output)
    finally:
        record['finished_at'] = time.time()
        write_json(output/'preview.json',record)
    return record


def stop(output):
    output = Path(output).resolve()
    record = json.loads((output/'preview.json').read_text())
    if record.get('resources_removed'):
        return record
    cleanup(record,output)
    record['outcome'] = 'cleanup_error' if record['cleanup_errors'] else 'stopped'
    record['stopped_at'] = time.time()
    write_json(output/'preview.json',record)
    return record

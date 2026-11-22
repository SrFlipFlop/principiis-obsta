# Development runtime and preview (#40)

Implemented 2026-11-16 for development rehearsals under the [approved baseline
specification](../BASELINE_PILOT_SPEC.md). Runtime preparation, runtime qualification,
live Codex development and preview acceptance are separate evidence. The fake-Docker
regression tests establish controller behavior; they do not qualify Docker containment,
subscription access or an actual generated portal. A scoped live launch still needs
the authorization required by issue #40.

`DevelopmentRuntime` uses the local Docker daemon at
`unix:///var/run/docker.sock`. It never inherits a Docker context, API credentials,
host home or user Docker configuration. The development image must be a prepared
local image identified by its complete `sha256:` ID. Its dependency/toolchain versions
are fixed by that image; build preparation may use the network, runtime never pulls.

Prepare the included toolchain image from a resolved **registry reference and digest**:

```bash
tar -C fixtures/development -cf - Dockerfile .dockerignore | docker build \
  --build-arg PYTHON_IMAGE=python@sha256:RESOLVED_REGISTRY_DIGEST \
  --build-arg CODEX_VERSION=0.169.0 -t principiis-development:qualification -
docker image inspect principiis-development:qualification
```

Record the real base digest, resulting local image ID, build logs and tool versions.
BuildKit does not accept a bare local image ID as a registry base reference. The
recipe prepares Python 3.12, SQLite, Flask 3.1, Git, Node/npm, a compiler toolchain,
bubblewrap and ordinary Codex. Other compatible application dependencies remain the
coding agent's choice. Do not include task files, researcher instructions, generated
applications, user configuration or credentials in the build context. Installed Codex
0.169.0 help and package metadata were inspected locally on 2026-11-16; this is the
version selected for this recipe, not a claim that it is the latest release.

A runtime JSON has exactly these fields:

```json
{
  "version": "1",
  "docker": "/snap/bin/docker",
  "image": "sha256:REPLACE_WITH_64_HEX_LOCAL_IMAGE_ID",
  "auth_file": "/operator/clean-subscription/auth.json",
  "clean_runtime_review": "PATH_OR_IDENTIFIER_OF_THE_RUNTIME_REVIEW"
}
```

The authentication file must be a separately provisioned regular file. The controller
does not read its contents. It mounts only that file and the current application's
workspace. The container copies authentication into an otherwise empty temporary
Codex home; no account files are copied back. Before starting development, the
container calls `codex login status` and requires the installed CLI's
`Logged in using ChatGPT` status. Its raw status stays inside the container. Other
authentication modes, unknown output and failed status checks abort the attempt with
a generic error before the model command. This guard does not verify account capacity
or whether a stored refresh token still works. The disposable container does not save
renewed credentials back to the private auth file. An old file can therefore produce
an incomplete attempt even when `codex login status` reports ChatGPT authentication.
Refresh the private auth file before an explicit `--retry`; preserve the failed attempt.

Each attempt uses a fresh container/home, `codex exec --ephemeral`, an empty user
configuration and no external conversations, skills, rules or memory. The adapter
omits model/reasoning overrides and records effective values as unknown. It uses
ordinary workspace-write permissions with network access and live documentation
search. The agent sees cumulative request text on stdin and its retained project;
future requests, controller records and evaluation artifacts are not mounted. The
container runs as a nonroot UID matching the host operator (UID 1000 when the
controller runs as root), with a read-only root, temporary home/tmp, dropped
capabilities, no new privileges and bounded CPU/memory/process resources. There is
no development-stage time limit. The adapter attempts forced removal after the stage,
including interruption. Cleanup errors remain separate from the genuine process exit;
a successful completed candidate cannot be regenerated solely because cleanup failed.
Before starting Docker, `runtime.json` beside the workspace records the allocated
container and exact cleanup argv. After a hard controller death, or a retained cleanup
error, run that cleanup command before retrying. The controller cannot execute cleanup
after SIGKILL or power loss; the sidecar makes any orphan discoverable. Keep all
original partial workspace/log evidence.

For the installed CLI, the adapter selects a `development` permissions profile that
extends built-in `:workspace` and sets `network.enabled=true`, using
`default_permissions="development"`. Execution and sandbox controls share the exact
same settings. An explicit `:workspace` diagnostic ignores the legacy
`sandbox_workspace_write.network_access` override; the retained controls exposed that
mismatch. Model and reasoning remain at harness defaults.

Development `/tmp` and the fresh home tmpfs explicitly allow executable files so
ordinary temporary build tools and user-local executables can run. Both retain
nosuid/nodev, bounded size and disposable contents. The inner workspace profile's
write permissions are unchanged. This development-only setting is recorded in adapter
version/fingerprint and execution evidence; preview keeps its previous tmpfs policy.
Preflight executes a temporary tool inside Codex's sandbox, and the opt-in runtime
control additionally executes a user-local tool in the outer container.

Image inspection rejects declared volumes/build hooks and unrecognized environment
names. Model-free preflight checks the image identity and Codex version, then actually
enters the ordinary Codex workspace sandbox. It checks workspace writes, denial of
writes to an otherwise writable path outside the workspace, Python virtual-environment
creation/execution, SQLite, Node and Git. It attests exact interpreter paths in the
fixed image for snapshot preservation. Failure aborts before allocating a development
attempt or mounting authentication. Diagnostic timeouts bound these controls, not model
development. These checks supplement the declared clean-runtime review; they cannot
prove that arbitrary image contents are clean. Review the image for baked credentials,
instructions and task content.

The development adapter uses the versioned default-deny
[`fixtures/development/seccomp_profile.json`](../../fixtures/development/seccomp_profile.json).
It derives from the repository's attributed Playwright profile and adds the mount
operations needed by bubblewrap in its unprivileged user namespace, modern path/access
syscalls, and a `clone3` ENOSYS fallback. The outer nonroot UID, dropped capabilities,
read-only root and no-new-privileges remain enforced. This policy exposes additional
kernel operations compared with Docker's default; passing controls is not proof
against kernel or container escapes. Preview keeps its existing policy. The policy
digest enters adapter version/fingerprint, execution evidence and the cleanup sidecar;
changing it prevents silent continuation of an existing development run. See the
attribution and modification record in
[`fixtures/development/NOTICE`](../../fixtures/development/NOTICE).
[Docker's seccomp documentation](https://docs.docker.com/engine/security/seccomp/)
describes the default-deny and custom-profile behavior (checked 2026-11-16).

Development records retain measured stage time, redacted CLI events, requested
settings, image/container identities and exit status. Process-group RSS covers the
host Docker client only. Separate `container_memory` evidence samples Docker's
formatted working-set usage, including every container process; this is not RSS or a
guaranteed peak. Missing samples stay unknown. Neither field measures hosted model
RAM. Spending stays unknown. Snapshots retain ordinary virtual environments using
exact interpreter-link bytes bound to the attested image; the host never follows
those links. Restore and preview require that same image. Other absolute/escaping
links and special files remain unsupported, with incomplete-attempt workspace/log
evidence retained. See [snapshot/environment semantics](SNAPSHOT_ENVIRONMENTS.md).

Preview uses a separately versioned JSON so its startup settings cannot change frozen
development provenance:

```json
{
  "version": "1",
  "docker": "/snap/bin/docker",
  "preview": {
    "image": "sha256:REPLACE_WITH_64_HEX_LOCAL_IMAGE_ID",
    "command": ["python", "app.py"],
    "container_port": 8123,
    "host_port": 0,
    "ready_path": "/ready",
    "startup_timeout_seconds": 30
  }
}
```

Use an image that already has the generated application's compatible dependencies.
A retained virtual environment can supply dependencies installed by the coding agent;
use its interpreter in the preview command and retain the development image ID.
Preview never installs dependencies or runs application commands on the controller
host. Additional image preparation must preserve that boundary. The included image
has Flask, but cannot anticipate every dependency a real agent may select.

`preview.start(snapshot, config_path, new_output)` validates the retained snapshot,
copies it into a new disposable workspace and starts the configured argv. Only that
copy is mounted; there is no authentication mount or hidden evaluator content. The
application uses a private IPv4 internal Docker bridge with
`com.docker.network.bridge.gateway_mode_ipv4=isolated` and IPv6 disabled. It has no
published port or external network interface. The isolated gateway mode removes the
host-facing bridge address; ordinary `--internal` alone retains a host-service path.
See [Docker's gateway-mode documentation](https://docs.docker.com/engine/network/port-publishing/#gateway-modes),
checked 2026-11-16. The controller inspects the actual network and fails closed if
these settings are absent.

A separate trusted TCP relay reaches the application through the private network and
publishes one port on `127.0.0.1` through an ordinary bridge. Its constant Python
standard-library program copies bytes between accepted connections and one fixed
application IP/port; it never interprets HTTP destinations or offers a generic proxy.
The relay receives no candidate files, credentials or other mounts. Python runs with
`-I -S` to disable user import configuration and installed-package startup hooks.
Kernel IPv4 forwarding is disabled in the relay. Both containers use read-only roots,
dropped capabilities, nonroot UIDs, temporary storage and resource bounds. The relay
script digest, fixed target and both container inspections are retained. An application
can contact the relay's private interface, but the only destination available through
the relay remains that same application endpoint.

`host_port: 0` requests an available loopback port. The controller checks the actual
relay binding and probes the declared path without following HTTP redirects. A missing
or null binding is a retained preview error. Readiness requires HTTP 200; it does not
imply that requested product features work. Image cleanliness, effective restrictions
and host-specific behavior require actual runtime qualification.

The new output retains `preview.json`, copied source and numbered Docker stdout/stderr
logs. Startup failure records `preview_error` and cleans allocated resources. A working
preview remains running until `preview.stop(output)` removes relay, application and network;
stopping is idempotent. The operator command prints the URL and exact cleanup command.
Copies and logs remain after cleanup. A failed candidate stays preserved; do not repair
it outside the development run or replay completed development to obtain a better app.

Routine verification:

```bash
python3 -m unittest discover -s tests -p test_development_runtime.py -v
python3 -m unittest discover -s tests -p test_preview.py -v
```

The preview tests substitute a loopback HTTP response because the normal controller
test sandbox prohibits listening sockets. Actual browser/backend startup and usable
preview evidence remain required before issue #40 acceptance.

Model-free Docker qualification is opt-in:

```bash
PO_PREVIEW_IMAGE=sha256:PREPARED_LOCAL_IMAGE_ID \
PO_PREVIEW_ROOT="$PWD/artifacts/mvp1-preview-controls" \
python3 -m unittest discover -s tests -p test_preview_containers.py -v
```

For the actual development sandbox and retained-venv preview controls, set
`PO_RUNTIME_IMAGE` to the prepared development image ID and run:

```bash
PO_RUNTIME_ROOT="$PWD/artifacts/mvp1-runtime-controls" \
  python3 -m unittest discover -s tests -p test_development_runtime_containers.py -v
PO_PREVIEW_ROOT="$PWD/artifacts/mvp1-preview-controls" \
  python3 -m unittest discover -s tests -p test_preview_containers.py -k retained_virtual -v
```

These controls mount no authentication and contact no model. Their fixed HTTP
application is an engineering control, never a replacement for a generated portal.

The first actual Docker 29.8.0 attempt, retained at
`artifacts/mvp1-runtime-qualification-20261116/preview`, failed because Docker did not
publish a usable port on the internal application network. The relay implementation
addresses that observed failure while keeping the application off an external network.
A subsequent harmless HTTP control passed in 23.837 seconds with evidence at
`artifacts/mvp1-preview-controls/http-control-23b0efd9e5444cb099f7b5d2c81c6aae`.
It checked effective application isolation, loopback reachability, binary POST bytes,
cookie response headers, snapshot integrity and complete cleanup. These controls
are not a generated portal or browser acceptance; final-version qualification evidence
is recorded separately when subsequent changes are exercised.

The final relay launch with `-I -S` was subsequently exercised by the same opt-in
HTTP control and passed in 23.197 seconds. Its separate retained evidence is
`artifacts/mvp1-preview-controls/http-control-15b0714fe273427096d71d5f9276f3f8`;
both containers and network were removed and the snapshot remained valid.

Toolchain preparation succeeded locally on 2026-11-16 as
`sha256:848b627634e2a1c082949371cc36b41b704af7e7863ccb1c8dff441d0e0f9048`
(`principiis-development:mvp1`). Model-free checks observed Codex 0.169.0, Python
3.12.12, Flask 3.1.3 and SQLite 3.46.1. The toolchain version probe passed, but the
initial nested workspace sandbox did not: default Docker policy rejected namespace
creation; a diagnostic with the existing evaluation seccomp profile reached a mount
operation denial. Those failures remain in the
[implementation verification record](../reviews/MVP_1_IMPLEMENTATION.md).
The subsequent [runtime fix verification](../reviews/MVP_1_RUNTIME_FIXES.md) records
the corrected policy and real model-free sandbox/environment controls. These controls
do not establish subscription access, actual generated-portal behavior or owner live
acceptance.

The owner's subsequent [authorized request-1 run](../reviews/ISSUE_40_LIVE_RUN_20261117.md)
completed actual subscription development and a restricted generated-portal preview.
On this Snap Docker host, `/tmp` was invisible to the daemon for bind mounting;
`/var/tmp/principiis-live-runs` was actually tested and used. Choose a run root visible
to both controller and local daemon. The original failed Docker launch remains in
the run's evidence.

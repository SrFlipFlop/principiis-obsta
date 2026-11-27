# Development runtime and preview (#40)

Implemented 2026-11-16 for development rehearsals; scope is in
[PROJECT.md](../../PROJECT.md). Runtime preparation, runtime qualification,
live Codex development and preview acceptance are separate evidence. The fake-Docker
regression tests establish controller behavior; they do not qualify Docker containment,
subscription access or an actual generated portal. Live Codex runs follow the hard
rules in [AGENTS.md](../../AGENTS.md).

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
ordinary workspace-write permissions. Web search is disabled and command network
access goes through the egress proxy (see [Network limits](#network-limits-75)). The agent sees cumulative request text on stdin and its retained project;
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
extends built-in `:workspace` and sets `network.enabled=true` (the container itself reaches only the egress proxy), using
`default_permissions="development"`. Execution and sandbox controls share the exact
same settings. An explicit `:workspace` diagnostic ignores the legacy
`sandbox_workspace_write.network_access` override; the retained controls exposed that
mismatch. Model and reasoning remain at harness defaults.

## Network limits (#75)

The repository is public, so the evaluated coding agent must not reach later requests
or published evaluator material ([ADR 0003](../adr/0003-evaluator-material-is-published-and-the-agent-is-network-limited.md)).

- **Web search is disabled** (`web_search = "disabled"`). Hosted search ignores every
  network limit below.
- **The development container joins only an internal Docker network**
  (`--internal`, IPv6 off), created per attempt. It has no route out.
- **A trusted egress proxy is the only way out.** It runs the standard-library program
  [`principiis/egress_proxy.py`](../../principiis/egress_proxy.py) (`python -I -S`) from
  the same pinned image, with no mounts, no credentials and the usual container
  restrictions. It sits on the internal network and the ordinary bridge. The development
  container gets `HTTPS_PROXY`/`HTTP_PROXY` (and lower-case forms) pointing at it.
  Tools that ignore the proxy variables, and direct DNS/TCP/UDP, fail closed.
- **`allowlist` mode** (every development run) forwards only the `domains` in
  [`fixtures/development/network_allowlist.json`](../../fixtures/development/network_allowlist.json)
  on ports 80 and 443. `*.example.org` matches subdomains only. HTTPS is tunnelled with
  CONNECT, so the proxy sees the domain, never the path; a package host that also serves
  arbitrary repositories (for example GitHub) cannot be allowed safely.
- **Only the Codex process reaches the model hosts.** The allowlist's `model_domains`
  (`api.openai.com`, `auth.openai.com`, `chatgpt.com`) are forwarded only for requests
  with `Proxy-Authorization: Basic base64("model:<token>")`, where the token is drawn with
  `secrets` for each attempt. Without it the proxy answers `403` and logs
  `"reason": "model host without the model credential"`. This stops a command from
  calling the model API itself with hosted web search turned on. `load_allowlist`
  requires a non-empty `model_domains` list of exact names and refuses a `domains` entry
  that equals or covers one of them.
  - The controller hands the token to the proxy and the development container by name
    (`--env PO_MODEL_TOKEN`; Docker reads the value from the controller's environment),
    so it is on no command line, log, evidence or `runtime.json`. The proxy removes
    it from its environment, never logs it and strips `Proxy-*` headers upstream.
  - The boot script builds `HTTPS_PROXY=http://model:<token>@<proxy>:3128` (and the
    other three proxy variables) for the Codex process only, and unsets `PO_MODEL_TOKEN`
    before `exec`.
  - The commands Codex runs get the token-less proxy:
    `shell_environment_policy.set={HTTPS_PROXY="http://<proxy>:3128",...}` and
    `shell_environment_policy.exclude=["PO_MODEL_TOKEN"]`.
  - The `development` profile denies reads of the Codex home:
    `permissions.development.filesystem={"/home/developer/.codex"="none"}`. It holds
    the login and Codex's shell snapshots, which capture the Codex process's environment.
  - Codex 0.169.0 runs each command under bubblewrap with `--unshare-pid` and a fresh
    `/proc`, so commands see only the sandbox helper and themselves, not the Codex
    process or the container's init.
  - The model-free preflight now proves this on every run. It passes a stand-in token
    exactly as `execute` does, and its probe, run as a command, requires no
    `PO_MODEL_TOKEN`, no credential in any proxy variable, no `://model:` or token
    variable in any visible `/proc/*/environ`, and `PermissionError` for the Codex home
    and its `auth.json`.
- **`log` mode** forwards every destination and records it. It exists only for the
  measurement below.
- Every decision is one JSON line in `egress.jsonl` beside the workspace, with
  `credential` = `valid`, `invalid` or `absent` (never the value). Execution evidence
  keeps the mode, allowlist and proxy digests, the allowed, refused and connected hosts,
  and `credentialed_hosts` (hosts requested with this attempt's token, so by the Codex
  process itself).
- The mode, allowlist digest, proxy digest and `model_credential` scheme
  (`per-run-token-v1: ...`, never the token) are part of `runtime_version`, together with
  `web_search`, the command environment policy (`command_environment`) and the
  permission settings, so an existing run cannot continue under a different network
  policy. The adapter is `docker-development-v4`.
- `runtime.json` (the allocation sidecar) also records the proxy container and network.
  `principiis cleanup` removes them after the development container.

**The allowlist is provisional.** It lists the ChatGPT/OpenAI endpoints (as
`model_domains`) and the package registries, but has not been measured. Build it from a logging-only run on the
disposable fixture request
[`fixtures/development/network_measurement_request.txt`](../../fixtures/development/network_measurement_request.txt)
(one pinned dependency from each ecosystem, one docs page, and a `NOTES.md` that records
success or failure per ecosystem; never a benchmark run).

### What is verified and what is not

Verified, model-free, on 2026-11-27 against `principiis-development:mvp1`
(`sha256:848b6276...`, Docker 29.10.0 Snap) by the opt-in control
`tests/test_egress_containers.py`, which starts the internal network and proxy through
`DevelopmentRuntime.start_egress`, as `execute` does:

- a client on the internal network without the proxy has no route: direct TCP and DNS fail;
- `pypi.org` and `files.pythonhosted.org` work through the proxy in `allowlist` mode;
- `github.com`, ports other than 80/443, loopback, private, link-local and IP-literal
  destinations get `403` and are logged as `refused`;
- the log has only method, host, port, decision and time (no path, query or headers);
- `pip install six==1.16.0` and `npm install left-pad@1.3.0` succeed with the
  provisional allowlist. `files.pythonhosted.org` is needed besides `pypi.org`.

Run it with `PO_RUNTIME_IMAGE=sha256:... PO_RUNTIME_ROOT=<dir the daemon can mount>
PO_EGRESS_CONTROL=1 python3 -m unittest discover -s tests -p test_egress_containers.py`
(about three minutes; it needs host internet, no login and no model).

Verified, model-free, on 2026-11-27 by the opt-in control
`tests/test_model_token_containers.py`. It ran against a local image
`sha256:eeaa4f1963909dd8383fc09d2f0af693557a040ae1d733787175f697f033542b`, built from
`fixtures/development/Dockerfile` without the Composer/Go/.NET layers on
`python@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b`
(Codex 0.169.0, linux/arm64), on Docker Desktop 29.9.3. Nothing could reach OpenAI:
- every proxy was cut from its outside network right after starting;
- the `codex exec` controls used a FAKE login with dummy tokens;
- the only answering model was a loopback stand-in inside the container.

Results:

- A command inside `codex sandbox --permission-profile development` gets `403` for
  `chatgpt.com`, `api.openai.com` and `auth.openai.com`. The log shows
  `refused`/`absent` with the reason.
- The same CONNECTs with the Codex process's credentialed proxy are `allowed`/`valid`
  (then `502`, since that proxy had no way out).
- From a command, `HTTPS_PROXY` has no credential and only PIDs 1 (the sandbox helper)
  and 2 are visible. No environment, `/proc/*/environ` or readable file under `/home`,
  `/tmp`, `/run`, `/workspace` or `/etc` contains the token. `auth.json` raises
  `PermissionError`.
- Real `codex exec`, with the fake login and a proxy that refused everything, sent its
  `chatgpt.com` traffic through `HTTPS_PROXY` with a valid model credential (its stderr
  shows the models refresh and an MCP request failing).
- Real `codex exec` with the loopback model ran one command through `exec_command`. That
  command got the token-less proxy, `403` for all three model hosts, no visible token
  and an unreadable `auth.json`. Codex exited 0.
- The existing egress and sandbox controls also passed on that image with the new proxy
  and probe.

Before the fix, the same stand-in-model control showed the command inheriting the
credentialed proxy URL and Codex's shell snapshot under
`$CODEX_HOME/shell_snapshots/` containing it.

Run it with `PO_RUNTIME_IMAGE=sha256:... PO_RUNTIME_ROOT=<dir the daemon can mount>
PO_EGRESS_CONTROL=1 python3 -m unittest discover -s tests -p test_model_token_containers.py`.
On Docker Desktop, also set:
- `PO_DIAGNOSTIC_UNMASK_PROC=1`: bubblewrap cannot mount its fresh `/proc` under Docker
  Desktop's masked `/proc` paths. The runtime's preflight fails closed there with
  `bwrap: Can't mount proc on /proc`.
- `PO_DIAGNOSTIC_TMPFS_WORKSPACE=1`: with the Codex-home denial, `codex exec` cannot
  remount a virtiofs workspace bind read-only (`Can't remount readonly on
  /workspace/.git`). It fails closed before any model request. A Docker volume
  (ext4) workspace worked in a scratch check.

The runtime never uses either switch.

**Not verified:**
- that real model traffic works through the credentialed proxy end to end. That needs an
  owner-approved live run; the measurement run will show it, because `egress.jsonl`
  then has `credential: valid` events for the model hosts.
- that `apply_patch` works under the Codex-home denial (the stand-in model is not
  offered that tool).
- that the Codex-home denial works with a Linux host bind mount (the owner's Snap
  Docker). The preflight uses a tmpfs workspace; a failure would stop the attempt
  before any model request.
- Composer, .NET and Go installs (the image has no such toolchains yet).
- the allowlist itself (still a guess until measured).

### Owner commands for the measurement run (the Codex machine)

This is a live subscription run and needs the owner's approval (AGENTS.md hard rule 3).
Use a dedicated login file (not `~/.codex/auth.json`) and a runs directory the Docker
daemon can mount (not `/tmp` with Snap Docker).

```bash
# 1. Nothing is started; calls no model and reads no login file.
python3 -m principiis.network_measurement preflight --config RUNTIME_JSON --runs-root RUNS_ROOT
# 2. The live run (only after the preflight says OK and you approve it).
python3 -m principiis.network_measurement --config RUNTIME_JSON --output RUNS_ROOT/network-measurement-01
# 3. Read the result. See "Recognising that Codex ignored the proxy" before trusting it.
cat RUNS_ROOT/network-measurement-01/measurement.json RUNS_ROOT/network-measurement-01/egress.jsonl
# 4. A draft allowlist that the runtime refuses until you edit it.
python3 -m principiis.network_measurement draft-allowlist \
    --measurement RUNS_ROOT/network-measurement-01/measurement.json --output DRAFT_ALLOWLIST.json
# 5. Review each host, delete every TODO marker, copy it over
#    fixtures/development/network_allowlist.json, and commit it.
# 6. Re-run the model-free control against the new allowlist.
PO_RUNTIME_IMAGE=sha256:... PO_RUNTIME_ROOT=RUNS_ROOT PO_EGRESS_CONTROL=1 \
    python3 -m unittest discover -s tests -p test_egress_containers.py
```

The draft never contains code-hosting hosts (GitHub, GitLab, Bitbucket), `golang.org`
hosts or IP literals; the command lists them so that you decide consciously. `connected_hosts`
counts only destinations that answered; an allowed host that never connected is not listed.

### Recognising that Codex ignored the proxy

The container has no other route, so a client that ignores `HTTPS_PROXY` fails closed
rather than leaking. Signs of that in a measurement or a later run:

- `result.json` (or `measurement.json`) shows the attempt as not completed;
- connection errors, timeouts or failed name resolution in `executor.stdout` and
  `executor.stderr` (`codex.stdout`/`codex.stderr` for the measurement);
- `egress.jsonl` is empty or missing, or contains no OpenAI host (`api.openai.com`,
  `chatgpt.com`, `auth.openai.com`) even though the model answered nothing;
- OpenAI hosts appear only as `refused` with `credential: absent` (Codex reached the
  proxy but did not send the model credential, so the model is unreachable), or
  `credentialed_hosts` in the evidence is empty.

Treat any of these as "Codex 0.169.0 does not honour the proxy for model or login
traffic". Do not widen the network to get around it. Record the failure, keep the
evidence, and ask for a design decision. Until a real measurement shows OpenAI hosts in
the log, that this works at all is a hypothesis.

The security-investigation reviewer (`principiis/investigation.py`) uses the same
runtime, so it is limited by the same allowlist.

**Known gaps, to resolve before tests go public (#75 item 2):**

- **Resolved: commands calling the model API.** The login was readable from commands
  and the model API was allowed, so a command could have called it with hosted web
  search turned on. Model hosts now need the per-attempt model credential, which only
  the Codex process holds, and commands cannot read the login (see above). What remains:
  - the Codex process itself still reaches the model hosts. Its own hosted search stays
    off only through `web_search = "disabled"`;
  - the barrier relies on bubblewrap's fresh `/proc`. Codex's `--no-proc` fallback
    would show the Codex process's environment, but the preflight probe would then fail;
  - in the stand-in run Codex also requested `ab.chatgpt.com` with the credential. It
    is not a model domain, so it was refused. The measurement decides whether it is
    needed: `draft-allowlist` lists OpenAI/ChatGPT hosts as `model_domains_measured`
    for the owner and never puts them in `domains`.
- **Hosts that serve arbitrary content.** `proxy.golang.org` is left off because it
  serves any public GitHub repository as a Go module, so Go module downloads fail
  until a safe option exists (a vetted module cache, for example). npm and PyPI also
  serve anything anyone uploads; that risk is lower and accepted for now. Packagist
  package downloads normally come from GitHub, so Composer installs may fail too.
- **Domain fronting.** The proxy checks only the CONNECT host, not TLS SNI or the
  HTTP `Host` header inside the tunnel.
- **DNS.** Whether Docker's embedded DNS forwards outside queries on `--internal`
  networks depends on the Docker version. If it does, DNS can carry data out. The
  controller checks only `Internal: true`; an opt-in container control should prove
  that external names do not resolve.
- **Other containers on the default bridge** can reach the proxy, which listens on
  all interfaces. In `log` mode that is unlimited egress for them.
- None of this has run against real Docker yet. Add an opt-in container control
  (refused host, allowed host, direct egress and DNS all checked, no model) before
  relying on it.

**Runs from before the model credential** are adapter `docker-development-v3`. Their
`runtime_version` has no `egress.model_credential` and their `egress.jsonl` lines have no
`credential` field; commands in them could reach the model hosts.

**Runs made before the network limits** had full network access through the ordinary Docker
bridge and live web search. Their results show it: execution evidence has
`runtime.network` = `bridge; ordinary development network access`, adapter
`docker-development-v2`, and `codex.settings.web_search` = `live`. Report them as such.

Workspaces already start without research-side Git history: step 1 starts empty, later
steps start from the agent's own previous snapshot, and only the workspace and the
login file are mounted.

Development `/tmp` and the fresh home tmpfs explicitly allow executable files so
ordinary temporary build tools and user-local executables can run. Both retain
nosuid/nodev, bounded size and disposable contents. The inner workspace profile's
write permissions are unchanged. This development-only setting is recorded in the adapter
version (each result's `runtime_version`) and execution evidence; preview keeps its previous tmpfs policy.
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
digest enters the adapter version (`runtime_version`), execution evidence and the cleanup sidecar;
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
[implementation verification record](../archive/reviews/MVP_1_IMPLEMENTATION.md).
The subsequent [runtime fix verification](../archive/reviews/MVP_1_RUNTIME_FIXES.md) records
the corrected policy and real model-free sandbox/environment controls. These controls
do not establish subscription access, actual generated-portal behavior or owner live
acceptance.

The owner's subsequent [request-1 run](../archive/reviews/ISSUE_40_LIVE_RUN_20261117.md)
completed actual subscription development and a restricted generated-portal preview.
On this Snap Docker host, `/tmp` was invisible to the daemon for bind mounting;
`/var/tmp/principiis-live-runs` was actually tested and used. Choose a run root visible
to both controller and local daemon. The original failed Docker launch remains in
the run's evidence.
Before mounting credentials or invoking Codex, each execution now probes the exact
workspace bind from the daemon with no network or authentication. A failure reports
the workspace path and asks for a daemon-visible run root without allocating an
attempt. The probe checks mount visibility; it does not qualify subscription access.

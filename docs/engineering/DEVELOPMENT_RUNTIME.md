# Development runtime and preview (#40)

Implemented 2026-11-16 for development rehearsals; scope is in
[PROJECT.md](../../PROJECT.md). Runtime preparation, runtime qualification,
live Codex development and preview acceptance are separate evidence. The fake-Docker
regression tests establish controller behavior; they do not qualify Docker containment,
subscription access or an actual generated portal. Live Codex runs follow the hard
rules in [AGENTS.md](../../AGENTS.md).

`DevelopmentRuntime` uses the local Docker daemon at
`unix:///var/run/docker.sock`, or at the Unix socket that `runtime.json` names in
`docker_socket` (see [Docker host settings](#docker-host-settings-docker-desktop)). It
never inherits a Docker context, `DOCKER_HOST`, API credentials, host home or user
Docker configuration. The development image must be a prepared
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

A runtime JSON has exactly these fields, plus the optional Docker host settings below:

```json
{
  "version": "1",
  "docker": "/snap/bin/docker",
  "image": "sha256:REPLACE_WITH_64_HEX_LOCAL_IMAGE_ID",
  "auth_file": "/operator/clean-subscription/auth.json",
  "clean_runtime_review": "PATH_OR_IDENTIFIER_OF_THE_RUNTIME_REVIEW"
}
```

### Docker host settings (Docker Desktop)

Three optional fields adapt the runtime to Docker Desktop. Leave them out on a Linux
Docker Engine: each default is the behaviour before they existed.

```json
{
  "docker_socket": "/Users/OPERATOR/.docker/run/docker.sock",
  "proc": "unmasked-for-nested-sandbox",
  "workspace_mount": "volume"
}
```

- **`docker_socket`** (default `/var/run/docker.sock`): the absolute path of the local
  daemon's Unix socket; `docker context inspect` shows it (Desktop:
  `$HOME/.docker/run/docker.sock`). The socket was hard-coded so that a `DOCKER_HOST`,
  Docker context or CLI configuration can never send the login and workspace to another
  (possibly remote) daemon. That still holds: the controller passes
  `--host unix://<path>` on every call with a cleaned environment, and the value must be
  an existing Unix socket, never a URL (`tcp://`, `ssh://`, `unix://...` are refused),
  so it can only name a local daemon. It is resolved, used for every Docker call made
  with the loaded configuration (including `principiis cleanup` and the measurement
  commands), saved in `runtime.json`'s cleanup argvs, and recorded in execution evidence
  (`runtime.docker_socket`). It is not part of `runtime_version`: it selects the daemon,
  not the policy, and it is a personal path.
- **`proc`** (default `docker-default`): `unmasked-for-nested-sandbox` adds
  `--security-opt systempaths=unconfined` to the containers that run the Codex sandbox
  (the two preflights and the development container), never to the egress proxy, the
  probes or the loader. See *Why /proc must be unmasked* below for the trade-off.
- **`workspace_mount`** (default `bind`): `volume` gives each attempt its own Docker
  volume instead of a bind of the host workspace. See *Volume workspace* below.

`proc` and `workspace_mount` are part of `runtime_version` (`docker_host`) and of the
execution evidence (`runtime.docker_host`, `runtime.workspace`), so a run cannot
continue under different settings.

**Why /proc must be unmasked.** Codex 0.169.0 runs each command under bubblewrap with
`--unshare-pid` and a fresh `/proc`; that `/proc` is what hides the Codex process (and
its model token) from commands. The kernel allows a new `proc` mount in an unprivileged
user namespace only if the existing `/proc` is fully visible: every mount over it is
locked when bubblewrap enters its user namespace, and any locked mount that hides part
of it (anything but an empty directory) makes the new mount "too revealing" (`EPERM`).
Docker's default masks (`/dev/null` over `/proc/kcore`, `/proc/keys`,
`/proc/timer_list`, `/proc/interrupts`; tmpfs over `/proc/scsi`, `/proc/acpi`;
read-only binds of `/proc/sys`, `/proc/bus`, `/proc/fs`, `/proc/irq`,
`/proc/sysrq-trigger`) are such mounts, so bubblewrap fails with
`bwrap: Can't mount proc on /proc: Operation not permitted` and the preflight stops the
attempt. This is a kernel rule, not a Desktop one; it was observed on Docker Desktop's
LinuxKit kernel (7.0.14). The Linux Snap Docker runs predate the `/proc` probe, so
whether they used a fresh `/proc` is unverified (Codex has a `--no-proc` mode "for
restrictive container environments", which the probe now refuses). If the owner's
Linux preflight fails the same way, the same setting applies there.

No narrower option was found: Docker refuses any mount under `/proc`
(`--mount ...,dst=/proc/kcore`, `--tmpfs /proc/scsi`: "cannot be mounted because it is
inside /proc"), and any re-masking would itself make the new `proc` mount too
revealing again. Codex's `--no-proc` would show commands the Codex process's
environment. The trade-off, measured on Docker Desktop as the runtime UID with no
capabilities (`tests/test_development_runtime_containers.py` checks it on every run
with this setting):

- Commands see nothing more than before: inside bubblewrap they get a fresh, unmasked
  `/proc` on any host where the sandbox works at all. The masks only ever covered the
  outer processes (the boot script and the Codex process).
- In the outer container, newly readable: `/proc/interrupts`, `/proc/scsi`, `/proc/keys`
  (only keys the runtime UID may view; the seccomp profile still denies `keyctl`, so no
  key contents) and `/sys/firmware` (the VM's firmware tables). Still
  unreadable: `/proc/kcore`, `/proc/timer_list` (root-only, `EACCES`);
  `/proc/sysrq-trigger` cannot be opened for writing.
- `/proc/sys` becomes a read-write mount, but no file in it can be written: writing each
  file's own current value back fails for all of them (only
  `/proc/sys/kernel/ns_last_pid` opens for writing; the write needs `CAP_SYS_ADMIN`).
  Inside the sandbox, commands can write only sysctls of bubblewrap's own IPC and PID
  namespaces (`kernel.shm*`, `msg*`, `sem`, `fs.mqueue.*`, `kernel.pid_max`,
  `ns_last_pid`, `cad_pid`), as on any host where the sandbox works.
- On a Linux host with the operator's UID, `/proc/keys` in the outer container would
  list that user's key descriptions; Docker Desktop's VM holds none.

**Volume workspace.** On Docker Desktop, `codex exec` with the Codex-home denial failed
at session start on a bind-mounted workspace that already held a repository directory
(`Can't remount readonly on /workspace/.git`; again in a scratch check as
`bwrap: Can't mount tmpfs on /workspace/.agents: No such file or directory` from the
AGENTS.md loader's filesystem sandbox helper). Desktop shares host directories through
its `fakeowner`/virtiofs file system, where bubblewrap's create-then-mount of protected
paths (`.git`, `.agents`, `.codex`) is unreliable; with the same seeded workspace the
failure did not always reproduce. The same steps always worked on a Docker volume
(ext4 in the VM) and on a tmpfs. With `workspace_mount: volume`, `execute`:

1. creates the volume `po-development-ws-<token>` and a loader container
   `po-development-load-<token>` that is created but never started (no network,
   read-only root, no capabilities, the runtime UID), mounting the volume root;
2. copies the workspace in as a tar archive (`docker cp -a`, so files belong to the
   runtime UID; symlinks are not followed);
3. mounts only the volume's `workspace` subdirectory at `/workspace`
   (`volume-subpath`, Docker Engine 26 or later), so `/workspace` itself belongs to the
   runtime UID; the host workspace is never mounted;
4. after the container exits (any status), copies `/workspace` back through the loader
   and replaces the host workspace with it, so deletions come back too. The controller
   extracts only directories, regular files, symlinks (byte for byte, never followed),
   hard links inside the tree and FIFOs; it refuses absolute names, `..` and any path
   under a symlink, and drops set-ID and sticky bits. It extracts into a fresh
   `.workspace-copy-<token>` beside the workspace and swaps it in only when complete;
5. removes the development container, the proxy, both networks, then the loader and the
   volume (`principiis cleanup` does the same from `runtime.json`, which records
   `workspace_volume` and `workspace_cleanup_argvs`).

If the copy back fails, the attempt is not completed (`exit_status` is null,
`process_exit_status` keeps Codex's, `error` says why), the host workspace stays as it
was before the attempt, and the loader and volume are kept (`runtime.json` state
`cleanup_error`) for inspection until `principiis cleanup` removes them. The pipeline
snapshots the copied-back workspace exactly as it snapshots a bind-mounted one, and no
bind-visibility probe is needed. Differences from a bind: the volume has no
`nosuid`/`nodev` (no capabilities and `no-new-privileges` still apply), and Codex's
empty protected-path mount points (`.agents`, `.aws`, `.codex`) come back as empty
directories (on Desktop's file sharing they disappeared; on a Linux ext4 bind they are
expected to stay, unverified).

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
[NETWORK_SANDBOX.md](NETWORK_SANDBOX.md) explains the layers below and the attacks tried
against them for readers new to this repository; [ADR 0004](../adr/0004-command-egress-pypi-gateway-codex-only-model-credential-docker-desktop-settings.md)
records the PyPI gateway, model credential and Docker Desktop decisions.

- **Web search is disabled** (`web_search = "disabled"`). Hosted search ignores every
  network limit below.
- **The development container joins only an internal Docker network**
  (`--internal`, IPv6 off), created per attempt. It has no route out.
- **A trusted egress proxy is the only way out.** It runs the standard-library program
  [`principiis/egress_proxy.py`](../../principiis/egress_proxy.py) (`python -I -S`) from
  the same pinned image, with no mounts, no login, only the per-attempt model token
  (below) and the usual container restrictions. It starts on the internal network alone, listens only on its address
  there (the controller checks the `listening` log line against Docker's view), and then
  joins its own per-run outside network `po-development-out-<token>` (IPv6 off). It never
  joins the default bridge, so other containers cannot reach it. The development
  container gets `HTTPS_PROXY`/`HTTP_PROXY` (and lower-case forms) pointing at it.
  Tools that ignore the proxy variables, and direct DNS/TCP/UDP, fail closed.
- **The proxy has a stable name, `egress-proxy`.** It is created with
  `--network-alias egress-proxy` on the internal network, and every variable commands
  get names it by that alias, never by its per-attempt address:
  `HTTPS_PROXY=http://egress-proxy:3128` (and the other three), `NO_PROXY`/`no_proxy`
  `localhost,127.0.0.1,::1,egress-proxy`, and the PyPI gateway variables below. Lockfiles
  that record the index URL (`uv.lock`, `poetry.lock`, a Poetry source in
  `pyproject.toml`) therefore record `http://egress-proxy:3128/pypi/simple/`, which is
  valid in every later attempt; before, they recorded the proxy's address, which changes
  with each attempt's network. The proxy variables use the alias too, so the command
  environment is the same in every attempt and `runtime_version` records it literally.
  Docker's embedded DNS answers the alias on the internal network only (it does not
  exist on the proxy's outside network) and still resolves no external name there. The
  controller still checks the proxy's `listening` address against Docker's view of its
  internal address; the alias only names that address. The proxy treats absolute-form
  requests to `http://egress-proxy:3128/pypi/...` as gateway requests, like those to its
  own address. In `log` mode a CONNECT to `egress-proxy` is refused (`non-public
  address`).
- **`allowlist` mode** (every development run) forwards only the `domains` in
  [`fixtures/development/network_allowlist.json`](../../fixtures/development/network_allowlist.json)
  on ports 80 and 443, and its `model_domains` only to the Codex process (below).
  `*.example.org` matches subdomains only. HTTPS is tunnelled with CONNECT, so the proxy
  sees the domain, never the path; a package host that also serves arbitrary
  repositories (for example GitHub) cannot be allowed safely.
  - **Never-allow list.** `NEVER_ALLOW` in `egress_proxy.py` names GitHub (github.com,
    githubusercontent.com, github.io, githubassets.com, ghcr.io, githubapp.com, github.dev,
    …) and services that mirror arbitrary public repositories (Go module proxies, jsDelivr,
    githack, statically, esm.sh, Gitpod, Sourcegraph, GitLab, Bitbucket, Codeberg, Gitee,
    archive.org, Software Heritage). `load_allowlist` refuses any entry of `domains` or
    `model_domains` that names one of them or a wildcard that covers one, bare `*`,
    wildcards with fewer than two labels after `*.` (`*.com`), and IP literals. The proxy
    refuses the same hosts, with or without the model credential, and ignores unsafe
    entries in either list even if the file was edited. `network_measurement
    draft-allowlist` never drafts them.
  - **SNI must match.** After `200` to a CONNECT, the proxy reads the client's TLS
    ClientHello and forwards it only if its server name equals the CONNECT host. No SNI,
    another SNI, Encrypted Client Hello and non-TLS bytes are refused (`reason`
    `no-sni`, `sni-mismatch`, `ech`, `not-tls`), on any port. This applies to the model
    hosts too: the credential is checked on the CONNECT, the SNI after it, so the Codex
    process cannot front another host through a model domain either.
  - **Plain HTTP** is forwarded only with exactly one `Host` header naming the
    request-line host and port, no `Transfer-Encoding`, and one request per connection
    (`Connection: close`; anything after the body is dropped). Otherwise `403`
    (`host-mismatch`, `unsupported-body`). `Proxy-*` headers are never forwarded.
  - **PyPI only through the gateway.** `pypi.org` and `files.pythonhosted.org` share
    Fastly with `raw.githubusercontent.com`, and the proxy cannot see the HTTP `Host`
    inside TLS, so a tunnel to them reached GitHub (Known gaps). They are
    *gateway-only* (`GATEWAY_ONLY` in `egress_proxy.py`, suffixes `pypi.org` and
    `pythonhosted.org`): `load_allowlist` refuses them, and wildcards covering them, in
    `domains` and `model_domains`; the proxy refuses a CONNECT to them
    (`reason: gateway-only host: use the PyPI gateway`) even if listed.
    Instead the proxy serves a read-only **PyPI gateway** on the same port (3128), over
    plain HTTP, on the internal network only:
    - `GET /pypi/simple/<project>/` → `https://pypi.org/simple/<normalised project>/`
      (PEP 503 name, normalised; no `/simple/` root, no JSON API);
      `GET /pypi/files/packages/<2 hex>/<2 hex>/<60 hex>/<file>` (wheel, sdist or
      `.metadata`) → `https://files.pythonhosted.org/packages/...`. Anything else (other
      methods or paths, `..`, percent-encoding, query strings, request bodies) gets `403`
      and never reaches upstream.
    - The gateway makes the upstream request itself with the standard library:
      `ssl.create_default_context()` (certificates and host name verified), SNI and
      `Host` fixed to the real host, only `Accept` (simple-API media types only),
      `Accept-Encoding: identity`, a fixed `User-Agent` and `Connection: close`. No
      client header is forwarded. Redirects, other statuses, answers with
      `X-GitHub-Request-Id` and unexpected content types get `502`; `404` is relayed.
    - Index pages are rewritten: HTML `href`s and JSON `url`s on
      `files.pythonhosted.org` point at `/pypi/files/...`, keeping `#sha256=` fragments
      and `hashes`, so pip still verifies every file; other file URLs are dropped. Index
      pages are capped at 64 MiB; files are streamed and capped at 1 GiB.
    - Same port with a path prefix, not a second port: the internal network already
      reaches exactly one listener, whose address the controller checks, and nothing
      else changes. Origin-form requests (`GET /pypi/...`) and absolute-form requests
      naming the proxy's own address or `egress-proxy` are the gateway; everything else
      is the proxy.
    - Commands get `PIP_INDEX_URL=http://egress-proxy:3128/pypi/simple/`,
      `PIP_TRUSTED_HOST=egress-proxy:3128`, `UV_DEFAULT_INDEX` (same URL),
      `UV_CACHE_DIR=/tmp/uv-cache` (Codex's sandbox keeps the home read-only, and uv
      refuses to start without a writable cache: `Failed to initialize cache at
      /home/developer/.cache/uv ... Read-only file system`), `UV_LINK_MODE=copy` (the
      cache on `/tmp` and the project on `/workspace` are different file systems, so uv
      cannot hard-link and otherwise warns `Failed to hardlink files; falling back to
      full copy` on every install; checked with and without) and
      `NO_PROXY`/`no_proxy` with the alias, both in
      `shell_environment_policy.set` and in the container environment. Tools that
      ignore these (Poetry, pipenv, a hard-coded `--index-url https://pypi.org/simple`)
      fail closed: the tunnel is refused. pip (install, `download`, sdist builds with
      `--no-binary`, which fetch their build backend through the gateway too) and uv
      (`uv pip install`, `uv add`; plain-http `UV_DEFAULT_INDEX` needs no
      `UV_INSECURE_HOST`) work with these variables alone. Poetry (2.5.1 checked) asks
      `https://pypi.org` itself and fails ("your network is not connected to the
      internet"); a benchmark that uses Poetry must make the gateway its primary source:
      `poetry source add --priority=primary gateway "$PIP_INDEX_URL"`. That writes
      `http://egress-proxy:3128/pypi/simple/` into `pyproject.toml`, valid in later
      attempts too.
    - The gateway serves in `log` mode too. Each request is one JSON line with
      `event: "gateway"`, the `route` (`simple`, `files` or `invalid`), the upstream
      `host`, the `decision` (`allowed`, `connected` with the upstream `status`, or
      `refused` with a `reason`), and never the path, project name, query or headers.
      `connected_hosts` therefore lists `pypi.org` and `files.pythonhosted.org`, and
      `draft-allowlist` never drafts them (gateway-only).
- **Only the Codex process reaches the model provider, in both modes.** The allowlist's
  `model_domains` (`api.openai.com`, `auth.openai.com`, `chatgpt.com`) are forwarded only
  for requests with `Proxy-Authorization: Basic base64("model:<token>")` (compared with
  `hmac.compare_digest`), where the token is drawn with `secrets` for each attempt.
  Without it the proxy answers `403` and logs
  `"reason": "model host without the model credential"`. This stops a command from
  calling the model API itself with hosted web search turned on. `load_allowlist`
  requires a non-empty `model_domains` list of exact names and refuses a `domains` entry
  that equals or covers one of them.
  - **Model-provider hosts.** `MODEL_PROVIDER` in `egress_proxy.py` lists the registrable
    domains OpenAI serves Codex, ChatGPT and the API from: `openai.com` (API, auth,
    platform, CDN), `chatgpt.com` (the ChatGPT backend Codex uses with a ChatGPT login,
    and subdomains such as `ab.chatgpt.com`), `chat.com` (an alias of ChatGPT),
    `oaistatic.com` (static assets) and `oaiusercontent.com` (user files); a suffix
    covers its subdomains. Any of them could lead a command to the model, and the
    shipped `model_domains` are only the three hosts Codex is known to need. So every
    host under them needs the model credential, in `log` mode as in `allowlist` mode;
    in `allowlist` mode it must also be a `model_domains` entry (else `403`, `reason`
    `model-provider host not in model_domains`). `load_allowlist` refuses `domains`
    entries that name or cover one. The list is not exhaustive (another provider would
    need its own key, which commands do not have); `allowlist` mode is default-deny
    regardless.
  - The controller hands the token to the proxy and the development container by name
    (`--env PO_MODEL_TOKEN`; Docker reads the value from the controller's subprocess
    environment), so it is on no command line, log, evidence or `runtime.json`. The proxy
    removes it from its environment, never logs it and strips `Proxy-*` headers upstream.
  - The boot script builds `HTTPS_PROXY=http://model:<token>@egress-proxy:3128` (and the
    other three proxy variables) for the Codex process only, and unsets `PO_MODEL_TOKEN`
    before `exec`.
  - The commands Codex runs get the token-less proxy:
    `shell_environment_policy.set={HTTPS_PROXY="http://egress-proxy:3128",...}` and
    `shell_environment_policy.exclude=["PO_MODEL_TOKEN"]`.
  - The `development` profile denies reads of the Codex home:
    `permissions.development.filesystem={"/home/developer/.codex"="none"}`. It holds
    the login and Codex's shell snapshots, which capture the Codex process's environment.
  - Codex 0.169.0 runs each command under bubblewrap with `--unshare-pid` and a fresh
    `/proc`, so commands see only the sandbox helper and themselves, not the Codex
    process or the container's init.
  - The model-free preflight proves this on every run. It passes a stand-in token
    exactly as `execute` does, and its probe, run as a command, requires no
    `PO_MODEL_TOKEN`, no credential in any proxy variable, no `://model:` or token
    variable in any visible `/proc/*/environ`, and `PermissionError` for the Codex home
    and its `auth.json`.
- **`log` mode** forwards and records every other destination, on any port, with the
  SNI it saw and whether a model credential came. It exists only for the measurement
  below. Even there it refuses, and logs as `refused` with a `reason`:
  - `NEVER_ALLOW` hosts (GitHub and its mirrors): `never-allowed host: ...`, so the
    measurement never reaches GitHub;
  - tunnels or plain HTTP to the `GATEWAY_ONLY` PyPI hosts:
    `gateway-only host: use the PyPI gateway`, so Fastly Host fronting is impossible
    there too (the gateway serves as in `allowlist` mode);
  - names that resolve to any non-public address (loopback, RFC 1918, link-local and
    cloud metadata `169.254.169.254`, shared/CGNAT, unspecified, multicast, IPv6
    ULA/link-local, IPv4-mapped forms; `localhost`, `host.docker.internal`, the
    proxy's own name and address, and shorthand forms such as `2130706433`):
    `non-public address`. The proxy resolves the name once, requires every address
    to be public, and connects to the address it checked. A name that does not resolve
    is still logged as a decision (`name does not resolve`, `502`), with its credential;
  - without the model credential: the shipped `model_domains` and every
    model-provider host (`model host without the model credential`), a tunnel whose
    TLS SNI names one whatever the CONNECT host (`model host in SNI without the model
    credential`: SNI fronting to the model API through another host on the same CDN),
    and plain HTTP whose `Host` header names one (`model host in Host header without
    the model credential`). The proxy gets the same per-attempt token as in `allowlist`
    mode (`network_measurement` runs through `execute`), so the Codex process reaches
    any OpenAI host it needs and the log records it with `credential: valid`, while
    commands get `403` for all of them;
  - Encrypted Client Hello (`ech`), which would hide a model host behind an outer SNI.
  Other SNI mismatches are only recorded. The `allowlist` mode never forwards such
  destinations anyway (names only, no IP literals); it also gives these reasons.
- Every decision is one JSON line in `egress.jsonl` beside the workspace, with
  `credential` = `valid`, `invalid` or `absent` (never the value) and, for refusals, a
  `reason`. Execution evidence keeps the mode, allowlist and proxy digests, the allowed,
  refused and connected hosts, and `credentialed_hosts` (hosts requested with this
  attempt's token, so by the Codex process itself).
- The mode, allowlist digest, proxy digest and `model_credential` scheme
  (`per-run-token-v1: ...`, never the token) are part of `runtime_version`, together with
  `web_search`, the command environment policy (`command_environment`, which now
  includes the PyPI gateway variables), the gateway scheme (`egress.pypi_gateway`,
  `pypi-gateway-v1: ...`), the model-provider hosts (`egress.model_provider_hosts`),
  the proxy alias (`egress.proxy_alias`), in `log` mode the refusals
  (`egress.log_policy`, `log-refusals-v2: ...`) and the model domains it enforces
  (`egress.model_domains`), the Docker host settings (`docker_host`), the permission
  settings and the adapter, so an existing run cannot continue under a different network
  policy. The adapter is `docker-development-v7`, the first that enforces all of this
  together: v6 (v5's SNI/Host checks, outside network and model credential, plus the
  PyPI gateway), the Docker Desktop host settings, `log` mode's refusals, model-provider
  hosts needing the credential in both modes, and the `egress-proxy` alias in the command
  environment. Its parts were developed on parallel branches that still said v6 (the host
  settings; the log-mode refusals with uv/Poetry); no run carries those. Two earlier
  parallel branches each used `docker-development-v4` for one half of v5.
- `runtime.json` (the allocation sidecar) also records the proxy container, the internal
  network and the outside network (`egress.outside_network`). `principiis cleanup`
  removes the development container, then the proxy, then both networks. Allocations
  made before the outside network existed have no `outside_network` and are still
  accepted.

**The allowlist is measured.** It was built on 2026-11-28 from a logging-only run on the
disposable fixture request
[`fixtures/development/network_measurement_request.txt`](../../fixtures/development/network_measurement_request.txt),
reviewed, fronting-checked and confirmed by a follow-up session under the enforced
allowlist; see [Live measurement (2026-11-28)](#live-measurement-2026-11-28). The owner's
final approval is the review of the file in its PR.

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

Verified again, model-free, on 2026-11-27 after the hardening (SNI/Host checks,
never-allow list, outside network, own-address listener) with the stock
`python:3.12-slim` image (`sha256:191083cd...`, Docker 29.9.3, Docker Desktop on macOS;
the control skips the Codex preflight, so any image with `python` works):

- from a client on the internal network without the proxy: direct TCP to `1.1.1.1` and
  to GitHub's address (resolved on the host and passed in), TCP to an IPv6 address,
  and DNS for `pypi.org` and `github.com` all fail; the client has no global IPv6 address;
- the internal network reports `Internal: true`, `EnableIPv6: false`; the proxy is on
  exactly the internal and its outside network, and listens only on its internal address;
- a container on the default bridge cannot connect to the proxy, and a container on the
  outside network cannot connect to the proxy's outside address;
- CONNECT to `github.com`, `api.github.com`, `raw.githubusercontent.com`,
  `codeload.github.com`, `objects.githubusercontent.com`, `gist.github.com` and GitHub's
  IP gets `403` (`refused`);
- a tunnel to `pypi.org` or `files.pythonhosted.org` whose TLS SNI is
  `raw.githubusercontent.com` is closed before any byte reaches the server
  (`sni-mismatch`; the client sees `SSLEOFError`); `pypi.org` with its own SNI returns
  `200` for `/simple/six/`;
- plain HTTP to `pypi.org` with `Host: raw.githubusercontent.com` gets `403`;
- `pip install six==1.16.0` succeeds (npm not checked: the stock image has no npm).

Run it with `PO_RUNTIME_IMAGE=sha256:... PO_RUNTIME_ROOT=<dir the daemon can mount>
PO_EGRESS_CONTROL=1 python3 -m unittest discover -s tests -p test_egress_containers.py`
(under a minute with a stock image; it needs host internet, no login and no model).
`PO_DOCKER` names the Docker CLI. On Docker Desktop, set the host settings the
controls write into their runtime config (`tests/support.py`, `runtime_host_settings`):
`PO_DOCKER_SOCKET=$HOME/.docker/run/docker.sock`,
`PO_RUNTIME_PROC=unmasked-for-nested-sandbox` and `PO_RUNTIME_WORKSPACE_MOUNT=volume`
(see [Docker host settings](#docker-host-settings-docker-desktop)). No wrapper is needed.

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
PO_EGRESS_CONTROL=1 python3 -m unittest discover -s tests -p test_model_token_containers.py`,
with the Docker Desktop host settings above on Desktop. The records below up to the
Docker host settings used two diagnostic switches instead (`PO_DIAGNOSTIC_UNMASK_PROC`,
which added `systempaths=unconfined` to every container, and
`PO_DIAGNOSTIC_TMPFS_WORKSPACE`, which replaced the workspace bind with a tmpfs); the
host settings replaced both.

Verified again, model-free, on 2026-11-28 after merging the hardening and the model
credential (adapter `docker-development-v5`), on the same scratch image and Docker
Desktop 29.9.3 with both diagnostics:

- `tests/test_egress_containers.py`: all controls above pass; the Fastly fronting probe
  still reaches GitHub (expected failure);
- `tests/test_model_token_containers.py`: commands get `403` for the three model hosts,
  see no token and cannot read `auth.json`; the Codex process's credentialed CONNECTs
  are `allowed`/`valid`; real `codex exec` sends `credential: valid` for `chatgpt.com`;
- a new control in it shows the credentialed tunnel still passes the SNI check. The
  isolated proxy resolves `chatgpt.com` to a TCP sink on the internal network (a Docker
  network alias), so nothing can reach OpenAI. With the credential, SNI `chatgpt.com` is
  forwarded (`tls` event, one ClientHello at the sink); SNI `pypi.org` and
  `raw.githubusercontent.com` are closed with `sni-mismatch`/`valid` and nothing reaches
  the sink; without the credential the CONNECT gets `403`.

Verified again, model-free, on 2026-11-28 after the PyPI gateway (adapter
`docker-development-v6`), on the same scratch image (`sha256:eeaa4f19...`, which has
npm 9.2.0) with both diagnostics, and on stock `python:3.12-slim` (`sha256:191083cd...`,
no npm), Docker Desktop 29.9.3. The records above that tunnel PyPI describe v5 and
earlier.

- `tests/test_egress_containers.py`, 10 tests, all pass on both images (the stock image
  skips only the npm half):
  - CONNECT to `pypi.org` and `files.pythonhosted.org` gets `403` (`gateway-only host`);
    the former expected failure, a tunnel to them with `Host: raw.githubusercontent.com`,
    now never gets a tunnel;
  - the generic fronting control: every `domains` host (`registry.npmjs.org`,
    `repo.packagist.org`, `packagist.org`, `api.nuget.org`), with its own SNI and
    `GET /SrFlipFlop/principiis-obsta/main/README.md` with
    `Host: raw.githubusercontent.com`, answers without GitHub content (`403` from npm
    and both Packagist hosts, `421` from NuGet; no `X-GitHub-Request-Id`);
  - `pip install six==1.16.0 requests==2.32.3` from a client on the internal network
    installs six, requests, urllib3, idna, certifi and charset-normalizer through the
    gateway only (gateway `connected` for `pypi.org`/`simple` and
    `files.pythonhosted.org`/`files`; no CONNECT to either); `npm install left-pad@1.3.0`
    still works;
  - the gateway serves `/pypi/simple/six/` (also with `Host: raw.githubusercontent.com`,
    a non-normalised name, and absolute-form to its own address) with file URLs
    rewritten to `/pypi/files/`, and refuses with `403`, never GitHub content:
    `/pypi/simple/../../...`, `/pypi/files/SrFlipFlop/...`, `/pypi/files/packages/../..`,
    `%2e%2e`, the bare README path, a query string, `/pypi/pypi/six/json`,
    `/pypi/simple/`, `POST`, `HEAD`, and absolute-form to `raw.githubusercontent.com` or
    `pypi.org`;
  - the log holds no path, query, project name or header (the log test now also sends
    gateway requests with sentinels).
- `tests/test_model_token_containers.py`, 5 tests, all pass. A new control runs
  `pip install six==1.16.0 requests==2.32.3` as a command inside
  `codex sandbox --permission-profile development`, with only the command environment
  (`shell_environment_policy.set`): it installs through the gateway. That proxy keeps its
  way out, but has no model token and no `domains`, so it cannot reach OpenAI.
- `python3 -m principiis.network_measurement fronting-check` on the shipped allowlist:
  four `PASS`, `FRONTING CHECK OK`. On a draft with `pypi.org`, `github.com` and
  `*.example.org` it reports `REFUSED`/`REFUSED`/`UNCHECKED` and exits 1.
- Positive control (scratch script, not in the suite): the same probe through a
  `log`-mode proxy, which then still tunnelled PyPI, flags `pypi.org` and
  `files.pythonhosted.org` as `FAIL` (`200`, `X-GitHub-Request-Id`) and passes
  `registry.npmjs.org`. So the probe does detect Fastly fronting.

Verified, model-free, on 2026-11-28 with the [Docker host settings](#docker-host-settings-docker-desktop)
(`docker_socket` = the Desktop socket, `proc: unmasked-for-nested-sandbox`,
`workspace_mount: volume`) instead of any diagnostic switch or socket wrapper, on Docker
Desktop 29.9.3 (LinuxKit 7.0.14, arm64), the scratch image `sha256:eeaa4f19...` and stock
`python:3.12-slim` (`sha256:191083cd...`):

- `tests/test_development_runtime_containers.py`: 1 test, OK (scratch image). The
  constructor preflight (with the `/proc` token probe) and the sandbox probe pass; the
  development container has empty masked/read-only path lists; the `/proc` exposure
  check above finds no writable `/proc/sys` file and unreadable `/proc/kcore`.
  Without `proc` (default) the same control still fails closed in its preflight with
  `bwrap: Can't mount proc on /proc: Operation not permitted`.
- `tests/test_egress_containers.py`: 10 tests, OK on the scratch image; 10 tests, OK
  (skipped=1, no npm) on `python:3.12-slim`.
- `tests/test_model_token_containers.py`: 5 tests, OK. Its two `codex exec` controls go
  through the real `DevelopmentRuntime.execute`, now with the volume workspace (proxy cut
  from its outside network, FAKE login, loopback stand-in model): commands get `403` for
  the three model hosts, see PIDs 1 and 2 only, no token, `PermissionError` for
  `auth.json`; Codex sends `credential: valid` for `chatgpt.com`.
- A scratch two-step check (not in the suite; same isolation, FAKE login, stand-in
  model): step 1 starts from a workspace holding a repository directory, its command
  writes a file and a `venv/bin/python -> /usr/local/bin/python` link; step 2 starts
  from a copy of step 1's result, deletes and creates files. Both `exit_status` 0,
  `copied_out: true`, `cleanup_state: removed`; the host workspace afterwards has the
  deletion, the new file and the byte-exact link. The same check with
  `workspace_mount: bind` also passed this time, which is why the bind failure is
  described as unreliable rather than certain.
- `python3 -m principiis.network_measurement preflight` with that runtime config:
  `PREFLIGHT OK` (no login read, nothing started).
- No `po-` container, network or volume remained afterwards.

Verified, model-free, on 2026-11-28 after the log-mode refusals (proxy change only;
adapter still `docker-development-v6`, `egress.log_policy` added for `log` mode), on the
scratch image (`sha256:eeaa4f19...`) and stock `python:3.12-slim`
(`sha256:191083cd...`), Docker Desktop 29.9.3, both diagnostics set:

- `tests/test_egress_containers.py`, 14 tests, all pass on both images (the stock image
  skips only the npm half). New controls:
  - a `log`-mode proxy: `registry.npmjs.org` gets `200`; the six GitHub hosts get `403`
    (`never-allowed host`), `pypi.org` and `files.pythonhosted.org` `403`
    (`gateway-only host`), and `127.0.0.1`, `localhost`, `10.0.0.1`, `172.17.0.1`,
    `192.168.1.1`, `169.254.169.254`, `2130706433`, the proxy's own address and its
    container name, and `host.docker.internal` `403` (`non-public address`). The
    fronting probe through it to both PyPI hosts never gets a tunnel. Only
    `registry.npmjs.org` is `connected`. Before the change the same control failed: the
    `log` proxy answered `200` to the GitHub CONNECTs;
  - uv 0.13.8, installed with pip through the gateway, then `uv venv` +
    `uv pip install requests==2.32.3` (requests, urllib3, idna, certifi,
    charset-normalizer) and `uv init` + `uv add six==1.16.0`, with only the command
    environment; the gateway served both routes and no PyPI tunnel opened;
  - `pip download six==1.16.0 requests==2.32.3`, `pip install --no-binary :all:
    six==1.16.0` (sdist build; setuptools comes through the gateway), and a PEP 691
    JSON index page (`application/vnd.pypi.simple.v1+json`, api 1.4, file URLs
    `/pypi/files/...`, `sha256` hashes, no foreign URL). pip and uv ask for JSON first,
    so every install above already used JSON pages;
  - Poetry 2.5.1: `poetry add requests==2.32.3` fails by default (CONNECT `pypi.org`
    refused, `gateway-only host`); after
    `poetry source add --priority=primary gateway "$PIP_INDEX_URL"` it installs.
- `tests/test_model_token_containers.py`, 5 tests, all pass on the scratch image. The
  Codex-sandbox gateway control now also
  installs uv with pip and runs `uv venv` and `uv pip install idna==3.10` (default
  cache) inside `codex sandbox --permission-profile development` with only
  `shell_environment_policy.set`. Without `UV_CACHE_DIR` it failed (read-only home);
  with it, it installs. uv warns that it falls back to copying from the cache
  (`UV_LINK_MODE=copy` would silence that; not set).
- `python3 -m principiis.network_measurement fronting-check` on the shipped allowlist:
  `registry.npmjs.org`, `repo.packagist.org`, `packagist.org` `PASS` (`403`),
  `api.nuget.org` `PASS` (`421`), `FRONTING CHECK OK`.

Verified, model-free, on 2026-11-28 on the integration branch (adapter
`docker-development-v7`: the Docker host settings, the log-mode refusals, model-provider
hosts needing the credential in both modes, the `egress-proxy` alias), Docker Desktop
29.9.3 (arm64), with the [Docker host settings](#docker-host-settings-docker-desktop)
(`PO_DOCKER_SOCKET`, `PO_RUNTIME_PROC=unmasked-for-nested-sandbox`,
`PO_RUNTIME_WORKSPACE_MOUNT=volume`) and `PO_EGRESS_CONTROL=1`, on two images: the
scratch image `sha256:eeaa4f19...` (no Composer/Go/.NET) and a full candidate built from
`fixtures/development/Dockerfile` on `python@sha256:191083cd...` for linux/arm64
(`sha256:a20bddedbaf0b3b1ab7eb7b59429e48e2b0234707fc1d01fddc377d2fe10b41b`, local
only; the .NET layer used the `linux-arm64` SDK tarball, see Known gaps). Results were
identical on both:

- `tests/test_development_runtime_containers.py`: 1 test, OK.
- `tests/test_egress_containers.py`: 16 tests, OK (npm present in both). New controls:
  - the alias: from a client on the internal network `egress-proxy` resolves to the
    proxy's checked address, while `pypi.org`, `github.com` and `chatgpt.com` do not
    resolve; on the proxy's outside network `egress-proxy` does not resolve;
  - a `uv.lock` from step 1 is valid unchanged later: `uv init` + `uv add six==1.16.0`
    behind one proxy (`172.18.0.2`), then the project copied (without `.venv`) into a
    new container behind a new proxy on a new internal network (`172.20.0.2`):
    `uv sync --locked` succeeds there, installs six 1.16.0, and `uv.lock` keeps the same
    SHA-256 (`registry = "http://egress-proxy:3128/pypi/simple/"`, no proxy address in
    it). Before the alias, `uv sync --locked` failed in this situation;
  - the `log`-mode control now runs with the shipped `model_domains` and also gets `403`
    `model host without the model credential` for `chatgpt.com`, `api.openai.com`,
    `auth.openai.com`, `ab.chatgpt.com` and `cdn.oaistatic.com` (that proxy has no token,
    so nothing could reach OpenAI), and `non-public address` for `egress-proxy`.
- `tests/test_model_token_containers.py`: 6 tests, OK. The commands inside
  `codex sandbox --permission-profile development` reach the proxy through the alias
  (Docker's DNS inside the sandbox); the uv install there shows `UV_LINK_MODE=copy` and
  no hard-link warning (a scratch check on the scratch image showed the warning without
  the variable and none with it). A new control starts a `log`-mode proxy with the
  shipped `model_domains` and a token, cut from its outside network: a command in the
  Codex sandbox gets `403` (`model host without the model credential`, `absent`) for
  `chatgpt.com`, `api.openai.com`, `auth.openai.com`, `ab.chatgpt.com`,
  `platform.openai.com`, `cdn.oaistatic.com` and `files.oaiusercontent.com`; the
  credentialed Codex-process proxy gets `502` for each (`refused`, `valid`,
  `name does not resolve`: allowed by policy, then no DNS and no route out).
- `python3 -m principiis.network_measurement fronting-check` on the shipped allowlist
  with the candidate: `registry.npmjs.org`, `repo.packagist.org`, `packagist.org`
  `PASS` (`403`), `api.nuget.org` `PASS` (`421`), `FRONTING CHECK OK`.
- `python3 -m principiis.network_measurement preflight` with a Docker Desktop
  `runtime.json` naming the candidate and a dedicated (real) login file: `PREFLIGHT OK`;
  the login check is `stat`-only (`content not read`), nothing is started that mounts
  it, and no model is called.
- An amd64 build of the same Dockerfile (the one the repository's .NET pin fits) runs
  only under emulation on this host, where the constructor preflight fails closed:
  `bwrap: Can't open source /: Function not implemented`.
- No `po-` container, network or volume remained afterwards.

What is still not verified is listed under Known gaps below.

### Owner commands for the measurement run (the Codex machine)

This is a live subscription run and needs the owner's approval (AGENTS.md hard rule 3);
so is the follow-up session in step 8. Use a dedicated login file (not
`~/.codex/auth.json`) and a runs directory the Docker daemon can mount (not `/tmp` with
Snap Docker). On Docker Desktop the login file must be in a directory Desktop shares
with its VM (it is bind-mounted read-only); the runtime never reads it on the host.

`RUNTIME_JSON` on Docker Desktop (macOS) has exactly this shape:

```json
{
  "version": "1",
  "docker": "/usr/local/bin/docker",
  "docker_socket": "/Users/OPERATOR/.docker/run/docker.sock",
  "image": "sha256:REPLACE_WITH_64_HEX_LOCAL_IMAGE_ID",
  "auth_file": "/Users/OPERATOR/DEDICATED_LOGIN_DIRECTORY/auth.json",
  "clean_runtime_review": "IDENTIFIER_OF_THE_IMAGE_REVIEW",
  "proc": "unmasked-for-nested-sandbox",
  "workspace_mount": "volume"
}
```

- `docker`: `which docker` (an executable symlink such as Desktop's
  `/usr/local/bin/docker` is kept as given);
- `docker_socket`: the `unix://` path of `docker context inspect desktop-linux
  --format '{{.Endpoints.docker.Host}}'`, without `unix://`;
- `image`: `docker image inspect --format '{{.Id}}' TAG` of an image whose platform
  matches the host. On Apple silicon that is linux/arm64; the repository's Dockerfile
  pins only the linux-x64 .NET SDK, so build the arm64 measurement candidate with the
  arm64 tarball and its SHA-512 from the same release metadata (a local variant, not a
  repository pin; see Known gaps):

```bash
mkdir -p BUILD_DIR && cp fixtures/development/.dockerignore BUILD_DIR/
sed 's/-linux-x64\.tar\.gz/-linux-arm64.tar.gz/' fixtures/development/Dockerfile > BUILD_DIR/Dockerfile
tar -C BUILD_DIR -cf - Dockerfile .dockerignore | docker build --platform linux/arm64 \
  --build-arg PYTHON_IMAGE=python@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b \
  --build-arg CODEX_VERSION=0.169.0 \
  --build-arg DOTNET_SDK_SHA512=3533a3869da219cac45c567aadac3d8e96cdf1c6a04fe1c1d5fdeefea5d45af8424488f0144730d11b4a751f7ad546fb11e4c2b2725cd8401efee726711f8f11 \
  -t principiis-development:measurement-candidate -
```

  (`3533a386...f8f11` is the `linux-arm64` hash of `dotnet-sdk-10.0.404` in
  `https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json`,
  release 10.0.15, checked 2026-11-28; the same file lists the repository's x64 pin.)

On a Linux Docker Engine leave out `docker_socket`, `proc` and `workspace_mount` unless
the preflight fails as described in *Why /proc must be unmasked*.

```bash
# 1. Nothing is started that mounts the login; calls no model and never opens the login file.
python3 -m principiis.network_measurement preflight --config RUNTIME_JSON --runs-root RUNS_ROOT
# 2. The live measurement (log mode; only after the preflight says OK and you approve it).
python3 -m principiis.network_measurement --config RUNTIME_JSON --output RUNS_ROOT/network-measurement-01
# 3. Read the result. See "Recognising that Codex ignored the proxy" before trusting it.
cat RUNS_ROOT/network-measurement-01/measurement.json RUNS_ROOT/network-measurement-01/egress.jsonl
# 4. A draft allowlist that the runtime refuses until you edit it.
python3 -m principiis.network_measurement draft-allowlist \
    --measurement RUNS_ROOT/network-measurement-01/measurement.json --output DRAFT_ALLOWLIST.json
# 5. Before approving, probe every drafted host for Host-header fronting to GitHub
#    (model-free; starts the proxy with no model domains and no token). Every host must
#    PASS; FAIL means GitHub answered through it, REFUSED/UNCHECKED must be resolved.
python3 -m principiis.network_measurement fronting-check --config RUNTIME_JSON --allowlist DRAFT_ALLOWLIST.json
# 6. Review each host, decide model_domains from model_domains_measured, delete every
#    TODO marker (and model_domains_measured), copy it over
#    fixtures/development/network_allowlist.json, and commit it.
# 7. Re-run the model-free controls against the new allowlist (the egress control
#    repeats the fronting probe for every `domains` host).
PO_RUNTIME_IMAGE=sha256:... PO_RUNTIME_ROOT=RUNS_ROOT PO_EGRESS_CONTROL=1 \
PO_DOCKER=/usr/local/bin/docker PO_DOCKER_SOCKET=/Users/OPERATOR/.docker/run/docker.sock \
PO_RUNTIME_PROC=unmasked-for-nested-sandbox PO_RUNTIME_WORKSPACE_MOUNT=volume \
    python3 -m unittest discover -s tests -p 'test_*_containers.py'
# 8. The follow-up session (live, needs approval): the same fixture request under the
#    enforced allowlist, as every development run. Its workspace NOTES.md shows which
#    ecosystem the allowlist breaks; egress.jsonl shows what was refused and why.
python3 -m principiis.network_measurement --config RUNTIME_JSON --output RUNS_ROOT/network-allowlist-01 --egress allowlist
```

`pypi.org` and `files.pythonhosted.org` appear in the measurement (through the gateway)
but are never drafted: they are gateway-only. Hosts the `log` proxy refused (GitHub and
its mirrors, PyPI tunnels, non-public addresses, model-provider hosts without the
credential) are in `refused_hosts`; `draft-allowlist` prints each as
`REFUSED during the measurement: <host>` and never drafts it. Their `reason` is in
`egress.jsonl`. Every host the Codex process reached with the model credential
(`credentialed_hosts`) and every connected model-provider host goes to
`model_domains_measured`, never to `domains`; the command prints each.
`draft-allowlist` refuses a record from the follow-up session (`egress_mode` is
`allowlist`).

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

### Live measurement (2026-11-28)

The live sessions on 2026-11-28 (owner-approved under hard rule 3, dedicated ChatGPT
login file, Docker Desktop 29.9.3 with the three host settings, arm64 measurement
candidate `sha256:a20bdded...`, adapter `docker-development-v7`, fixture request
`fixtures/development/network_measurement_request.txt`; no benchmark request):

1. **Measurement, `log` mode.** Codex completed the request. Every model request went
   through the credentialed proxy (`chatgpt.com` 28 times, `credential: valid`); Codex
   also reached `ab.chatgpt.com` and three `sdmntpr*.oaiusercontent.com` hosts with the
   credential. Refused: `github.com` and `api.github.com` (Composer's package download and
   its git fallback), `proxy.golang.org` (Go), and a tunnel to `pypi.org`. pip installed
   Flask, pytest and six through the PyPI gateway (13 index and 24 file requests); npm
   (`registry.npmjs.org`) and NuGet (`api.nuget.org`) worked; docs pages loaded.
   `draft-allowlist` proposed 12 hosts.
2. **Review and fronting check.** `fronting-check` on the draft **failed for
   `docs.python.org`**: it is on Fastly, and a tunnel to it with
   `Host: raw.githubusercontent.com` returned this repository's README. `pkg.go.dev`
   passed the probe but renders the GitHub README of any Go module. Both joined
   `NEVER_ALLOW`. The remaining 10 hosts pass, and are the committed
   `network_allowlist.json`; `model_domains` stayed at `api.openai.com`,
   `auth.openai.com`, `chatgpt.com`.
3. **Follow-up session, enforced allowlist** (`--egress allowlist`). Codex worked with
   only the three model domains; its requests to `ab.chatgpt.com` and
   `*.oaiusercontent.com` were refused (`model-provider host not in model_domains`,
   credential `valid`) without visible effect, so they stay out. Refused as never-allowed:
   `github.com`, `api.github.com`, `proxy.golang.org`, `docs.python.org`, `pkg.go.dev`;
   refused as unlisted: `six.readthedocs.io`, `www.php-fig.org`, `www.newtonsoft.com`.
   pip (gateway), npm and NuGet installs worked. Composer resolved `psr/log` but its
   download from GitHub was refused, as expected; Go failed at `proxy.golang.org`.

Findings for the development image (not network): in the Codex sandbox the home
directory is read-only, so the .NET SDK first failed with
`The system cannot open the device or file specified. : 'NuGet-Migrations'` until the
agent set `DOTNET_CLI_HOME`, `NUGET_PACKAGES` and `XDG_DATA_HOME` to temporary
directories; Go needed `GOCACHE` likewise. If the candidate image is adopted, set these
in the command environment.

**Known gaps (#75 item 2).** One list: what is open, then what was closed and how it
was verified.

Open, to resolve before tests go public:

- **Host fronting to OpenAI inside TLS in `log` mode.** The proxy sees the CONNECT
  host and the SNI, not the HTTP `Host` inside TLS. A command could open a tunnel to some
  other host on the same CDN as OpenAI, with that host's SNI, and send
  `Host: api.openai.com` inside TLS. Whether Cloudflare routes that across zones was not
  tested (it would contact OpenAI). A command still has no OpenAI credential (it cannot
  read the login), so it could not use the API without one. `allowlist` mode is not
  affected: there a command reaches only `domains` hosts that passed the fronting check.
- **The Codex process itself still reaches the model hosts.** Its own hosted search
  stays off only through `web_search = "disabled"`. The barrier against commands relies
  on bubblewrap's fresh `/proc`; Codex's `--no-proc` fallback would show the Codex
  process's environment, but the preflight probe would then fail. In the stand-in run
  Codex also requested `ab.chatgpt.com` and `*.oaiusercontent.com` with the credential:
  `allowlist` mode refuses them (not model domains), `log` mode forwards and records them.
  The 2026-11-28 enforced session ran fine without them.
- **The model-provider list is not exhaustive.** `MODEL_PROVIDER` names OpenAI's own
  domains. A host outside it that leads to the model (a reseller, Azure OpenAI) would need
  its own key, which commands do not have; `allowlist` mode is default-deny regardless.
- **Docker Desktop runs with explicit host settings.** The runtime works on Docker
  Desktop only with the three [Docker host settings](#docker-host-settings-docker-desktop);
  without them it fails closed in its preflight. What differs from a Linux Docker Engine
  with the defaults: the outer container's `/proc` is unmasked (the trade-off is
  documented there), the workspace is a copied volume instead of a bind (no
  `nosuid`/`nodev`; Codex's empty mount-point directories come back), and
  preview, restricted evaluation and evaluation cleanup do not read the settings (they
  still use `/var/run/docker.sock` and binds). Neither setting has been tried on the
  owner's Linux Docker, and there it is unverified whether the nested sandbox gets a
  fresh `/proc` without `proc: unmasked-for-nested-sandbox` and whether the Codex-home
  denial works with a bind-mounted workspace (`workspace_mount: volume` avoids that).
- **The Dockerfile's .NET layer is linux-x64 only.** On Apple silicon an amd64 image runs
  under emulation, where bubblewrap fails (`Can't open source /: Function not
  implemented`), so the preflight stops before any model request. The measurement
  candidate is a local arm64 variant built with the `linux-arm64` tarball and its
  published SHA-512 (see the owner commands). Making the recipe multi-architecture
  (one pinned hash per architecture) is not done.
- **Composer and Go installs fail by design.** Verified in the 2026-11-28 sessions:
  Composer resolves through Packagist but downloads from GitHub (`api.github.com`, then a
  `github.com` clone), both refused; Go fails at `proxy.golang.org`. A vetted cache or
  mirror would be needed for either. .NET (NuGet) installs work.
- **Hosts that serve arbitrary content.** `proxy.golang.org` is never allowed because it
  serves any public GitHub repository as a Go module, so Go module downloads fail until a
  safe option exists (a vetted module cache, for example). npm and PyPI also serve
  anything anyone uploads (the gateway does not change that: anyone could publish the
  repository's files as a PyPI project); that risk is lower and accepted for now.
  Packagist package downloads normally come from GitHub, so Composer installs may fail
  too. The never-allow list is not exhaustive; `allowlist` mode is default-deny
  regardless.
- **Encrypted Client Hello** is refused in both modes, including Chrome-style GREASE ECH,
  so a client that always offers ECH cannot use the proxy. No client in the image does.
- **Name resolution in `log` mode** happens at the proxy, through Docker's DNS on the
  outside network. A name that resolves to a mix of public and non-public addresses is
  refused as a whole.
- **`apply_patch` under the Codex-home denial** is unverified (the stand-in model is not
  offered that tool).

Closed:

- **Model hosts were not fronting-checked (closed 2026-11-28).** `fronting-check` now
  probes `model_domains` too, tunnelling with a throwaway model credential made for the
  check and sending `Host: raw.githubusercontent.com` with no login inside. On real
  Docker, `api.openai.com`, `auth.openai.com` and `chatgpt.com` (Cloudflare) each answered
  `403` with no GitHub content; the ten `domains` hosts passed again. `FRONTING CHECK OK`.
- **Real model traffic through the credentialed proxy (verified 2026-11-28).** Two live
  sessions (measurement and enforced allowlist) carried every Codex model request through
  the proxy with `credential: valid`; see [Live measurement](#live-measurement-2026-11-28).
- **The allowlist was a guess (closed 2026-11-28).** It is now measured, reviewed and
  fronting-checked. The fronting check caught `docs.python.org` (Fastly, returned
  GitHub content); it and `pkg.go.dev` are never-allowed.
- **Commands could reach the model hosts in `log` mode (closed in v7, verified
  2026-11-28).** The measurement ran with no `model_domains`, so a command could have
  called the model API with hosted web search. `log` mode now enforces the shipped
  `model_domains` and every model-provider host with the per-run credential, which the
  proxy gets exactly as in `execute`; it also refuses an SNI or `Host` naming one without
  the credential and Encrypted Client Hello. Commands get `403` for every OpenAI host;
  the Codex process's requests are forwarded and logged as `credential: valid`.
- **Lockfiles recorded the per-attempt gateway address (closed in v7, verified
  2026-11-28).** `uv.lock`, `poetry.lock` and a Poetry source recorded
  `http://<proxy address>:3128/...`, so `uv sync --locked` failed in a later step and a
  plain `uv sync` relocked. Commands now use the alias `egress-proxy`; a `uv.lock` from
  one attempt passes `uv sync --locked` unchanged behind a fresh proxy.
- **`log` mode tunnelled PyPI and reached GitHub and private addresses (closed
  2026-11-28).** It now refuses `NEVER_ALLOW`, `GATEWAY_ONLY` and non-public destinations
  and logs each refusal (see *`log` mode* above).
- **Host-header fronting through Fastly to GitHub is closed for PyPI (verified on real
  Docker, 2026-11-28).** The proxy sees the SNI but not the HTTP `Host` inside TLS.
  `pypi.org` and `files.pythonhosted.org` share Fastly with `raw.githubusercontent.com`:
  on 2026-11-27 a tunnel to `pypi.org` with SNI `pypi.org` and
  `Host: raw.githubusercontent.com` returned `200` with this repository's `README.md`
  (`X-GitHub-Request-Id`, `Via: 1.1 varnish`). The owner chose a registry gateway: PyPI
  is gateway-only (see *PyPI only through the gateway* above), so no tunnel to it
  opens, and the gateway sets SNI and `Host` itself
  (`test_host_header_fronting_through_pypi_is_closed_because_pypi_is_never_tunnelled`);
  `test_no_allowlisted_domain_fronts_github` probes every remaining `domains` host:
  `registry.npmjs.org` (Cloudflare) and both Packagist hosts (BunnyCDN) answer `403`,
  `api.nuget.org` `421`.

  **Adding another registry safely.** The SNI check cannot stop Host fronting, so every
  new `domains` host must pass `python3 -m principiis.network_measurement
  fronting-check --allowlist <candidate>` (step 5 of the measurement commands) and the
  container control. A host that `FAIL`s (GitHub answers through it, for example
  anything else on Fastly such as `pythonhosted.org` subdomains or `python.org`) must not
  be allowed; it needs a gateway like PyPI's or must be added to `GATEWAY_ONLY`/
  `NEVER_ALLOW`. A pass is a point-in-time observation: CDNs change, so re-run the
  check whenever the allowlist or the image changes. The probe asks only for
  `raw.githubusercontent.com`; other GitHub hosts behind the same CDN are covered only
  because a CDN that routes by `Host` would normally serve them all.
- **uv and Poetry through the gateway**: uv works with the command environment alone
  (uv 0.13.8, also inside the Codex sandbox); Poetry needs the gateway as its primary
  source (see above).
- **Commands calling the model API** (allowlist mode, 2026-11-27): the login was readable
  from commands and the model API was allowed. Model hosts now need the per-attempt model
  credential, which only the Codex process holds, and commands cannot read the login.
- **SNI-based domain fronting** (SNI must equal the CONNECT host), including through a
  credentialed model-host tunnel, and **plain-HTTP `Host` fronting**.
- **GitHub and its mirrors** are refused (never-allow list), for commands and for the
  Codex process alike, in both modes.
- **DNS** (external names do not resolve on the internal network, including
  `github.com`; only the proxy's alias does) and **IPv6** (no global address, no IPv6
  route).
- **Reachability of the proxy from the default bridge**: it has its own outside network
  and listens only on its internal address.

**Runs from before this enforcement** are recognisable by their adapter.
`docker-development-v3` runs have no SNI/Host checks, put the proxy on the default
bridge, have no `egress.model_credential` in `runtime_version` and no `credential` field
in `egress.jsonl`; commands in them could reach the model hosts. `docker-development-v4`
names one half of v5 on an unmerged branch only. v5 tunnelled PyPI; v6 commands named the
proxy by its address, and a v6 `log`-mode measurement (if any) let commands reach the
model hosts.

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

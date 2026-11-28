# Commands reach PyPI through a gateway and the model only through Codex; Docker Desktop needs explicit settings

The PyPI gateway was chosen by the owner on 2026-11-28, after the Fastly finding below. The model credential and the Docker Desktop settings were decided during the #75 implementation and are recorded here for review. The mechanism is explained in [NETWORK_SANDBOX.md](../engineering/NETWORK_SANDBOX.md); the verification records are in [DEVELOPMENT_RUNTIME.md](../engineering/DEVELOPMENT_RUNTIME.md#network-limits-75).

## Context

[ADR 0003](0003-evaluator-material-is-published-and-the-agent-is-network-limited.md) publishes the hidden tests and protects the evaluated coding agent with network limits instead: an internal Docker network whose only way out is an egress proxy with an allowlist. Three problems came up while building it.

- **Host fronting through PyPI.** HTTPS goes through `CONNECT`, and the proxy checks that the TLS SNI matches the `CONNECT` host, but it cannot see the HTTP `Host` header inside TLS. On 2026-11-27 a real-Docker probe opened a tunnel to `pypi.org` with SNI `pypi.org` and sent `Host: raw.githubusercontent.com`: Fastly answered `200` with this repository's `README.md` and `X-GitHub-Request-Id`. Any host on a CDN shared with GitHub can do this, and PyPI is one.
- **Commands could call the model API.** Codex must reach OpenAI, but the commands it runs share its container and its proxy. A command that reaches the model API can turn on hosted web search, which ignores every network limit. A model-free control also showed that a command inherited Codex's proxy settings and that Codex's shell snapshot under `$CODEX_HOME/shell_snapshots/` recorded them.
- **Docker Desktop.** On Docker Desktop, Codex's bubblewrap sandbox failed with `Can't mount proc on /proc: Operation not permitted`. The kernel refuses a fresh `proc` mount in an unprivileged user namespace while Docker's masks hide part of `/proc`. Bind-mounted workspaces on Desktop's shared file system also broke bubblewrap's mounts once the Codex home was denied. The fresh `/proc` is what hides the Codex process from commands, so it cannot simply be dropped.

## Decision

- **Commands reach PyPI only through a read-only gateway in the egress proxy.** `pypi.org` and `pythonhosted.org` are gateway-only: no allowlist may list them and the proxy never tunnels to them, in either mode. The proxy serves `/pypi/simple/<project>/` and `/pypi/files/packages/<hashed path>` over plain HTTP on the internal network, makes the upstream HTTPS request itself with certificate verification, a fixed host, path shape and header set, and rewrites file URLs back to itself with their hashes. Every other `domains` host must pass `network_measurement fronting-check` before it is allowed.
- **Model hosts need a per-run credential that only the Codex process holds.** The proxy forwards `model_domains`, and every host under OpenAI's registrable domains, only with `Proxy-Authorization` for a token drawn per attempt. The token goes to the Codex process's proxy URL only. Commands get the token-less proxy through `shell_environment_policy`, cannot see the Codex process (bubblewrap's PID namespace and fresh `/proc`) and cannot read the Codex home. Codex's own `web_search` stays disabled.
- **Docker Desktop is supported through explicit `runtime.json` settings, never by default.** `docker_socket` names a local Unix socket, `proc: unmasked-for-nested-sandbox` drops Docker's `/proc` masks only for the containers that run the Codex sandbox, and `workspace_mount: volume` copies the workspace through a per-attempt volume. Each default keeps the Linux behaviour, and `proc` and `workspace_mount` are part of `runtime_version`.

## Alternatives considered

The owner's choice of the gateway was recorded without stated reasons for rejecting the other two; the reasons below are the trade-offs as seen during the implementation.

- **TLS interception for PyPI** (a proxy CA trusted in the image, so the proxy can read and check `Host` inside TLS). Not chosen: the proxy would hold a CA key and parse all HTTPS for every host, every tool in the image would have to trust the CA, and a mistake would expose all traffic rather than one route. The gateway covers the one ecosystem that needed it with a fixed, small request shape.
- **Dropping PyPI** (no Python packages from the network). Not chosen: the document portal is a Python application, and the agent's ordinary choice of compatible libraries is part of the baseline ([ADR 0001](0001-separate-baseline-requests-from-security-expectations.md)).
- **Trusting commands not to call the model.** That leaves hosted search one `curl` away.
- **Codex's `--no-proc` mode on Docker Desktop.** It would let bubblewrap start, but commands could then read the Codex process's environment, including the credential. Unmasking `/proc` for the sandbox containers only exposes less: commands already see a fresh, unmasked `/proc` inside bubblewrap.

## Consequences

- Python tools must use the gateway: pip and uv do through `PIP_INDEX_URL` and `UV_DEFAULT_INDEX`; Poetry fails closed until the gateway is its primary source. Packages are still whatever anyone uploaded to PyPI; that risk is accepted for now.
- Each new registry needs a passing fronting check, repeated whenever the allowlist or image changes. A registry that fails needs its own gateway or must stay out.
- The barrier against commands relies on Codex 0.169.0's sandbox behaviour (PID namespace, fresh `/proc`, the permission profile). The model-free preflight checks it on every run, and a Codex upgrade must pass it again.
- Docker Desktop runs differ from Linux runs in recorded ways (`runtime_version.docker_host`): the outer container's `/proc` is unmasked and the workspace is a copied volume. Neither setting has been tried on a Linux Docker Engine.
- Still open: real model traffic through the credentialed proxy, fronting through the model hosts' CDN, and the measured allowlist. See the Known gaps in [DEVELOPMENT_RUNTIME.md](../engineering/DEVELOPMENT_RUNTIME.md#what-is-verified-and-what-is-not).

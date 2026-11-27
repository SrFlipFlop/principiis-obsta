# Development image with five-ecosystem toolchains (#75)

Status: **built and checked locally on 2026-11-27; not qualified, not adopted.**
`principiis-development:mvp1` (`sha256:848b6276...f9048`) is unchanged and remains the
pinned runtime. This record covers the candidate `principiis-development:mvp2-toolchains`.
Build recipe and runtime rules: [DEVELOPMENT_RUNTIME.md](DEVELOPMENT_RUNTIME.md).

## Why

mvp1 has only Python/pip, Node/npm, Git and curl. The #75 network measurement asks the
coding agent to use five package ecosystems, so Composer, the .NET SDK (NuGet) and Go were
missing. This candidate adds them and nothing else.

## What changed (`fixtures/development/Dockerfile`)

Two new layers after the unchanged mvp1 layer; user `1000:1000`, `/workspace`, `CMD`,
Codex 0.169.0, Python 3.12.12 and the Flask pin are unchanged.

| Tool | Source | Version installed |
| --- | --- | --- |
| PHP CLI + `mbstring xml curl zip` (openssl/phar/json built in), `unzip` | Debian 13 (trixie) packages | PHP 8.4.28 (`php8.4-cli 8.4.28-1~deb13u1`) |
| Composer | Debian package `composer` | 2.8.8 (`2.8.8-1+deb13u4`) |
| Go | Debian package `golang-go` -> `golang-1.24-go` | go1.24.4 (`1.24.4-1`) |
| .NET SDK (dotnet, NuGet, MSBuild) | official tarball, pinned in the Dockerfile | 10.0.404 (LTS, runtime 10.0.15) |

- **Debian packages** are authenticated by apt's signed `Release` metadata. They are *not*
  pinned to an exact package version (Debian removes old versions, and the existing mvp1
  layer is likewise unpinned). The Dockerfile instead fails the build unless the major/minor
  versions match (`go1.24.`, `Composer version 2.`, `PHP 8.4.`). Rebuilds therefore give the
  same minor line but can differ in Debian security patch level; the **image ID, not the
  recipe, is the pin**.
- **.NET** is downloaded from
  `https://builds.dotnet.microsoft.com/dotnet/Sdk/10.0.404/dotnet-sdk-10.0.404-linux-x64.tar.gz`
  and verified with the SHA-512 Microsoft publishes in its release metadata
  (`https://builds.dotnet.microsoft.com/dotnet/release-metadata/10.0/releases.json`, checked
  2026-11-27, release 10.0.15 dated 2026-11-10):
  `577d0eb17fec33d029104c5c63a1ab0accc3e28776274abef2218dbac5af18d2109b5406d26b31d76f5c245215e3ba0926a94c20246c672c41847c9e1eb1dc50`.
  The hash comes over the same TLS channel as the tarball, so it detects corruption and a
  stale mirror, not a compromised publisher. No detached signature was verified. The release
  index (`releases-index.json`, same date) lists .NET 10.0 as the active LTS; 8.0 and 9.0
  reached end of life on 2026-11-10. The SDK ships its own targeting packs and templates, so
  offline `dotnet new console` and `dotnet run` work.
- Go base-distro note: Debian trixie's Go is 1.24, older than the upstream line. A
  `go.mod` requiring a newer Go fails (see below). Upstream tarballs with published SHA-256 are
  the alternative if that matters; they were not used to keep the image smaller and simpler.

### Settings without new image environment names

`inspect_image` rejects environment names outside `IMAGE_ENVIRONMENT`
(`principiis/development_runtime.py`), so the image sets **no new `ENV`**:

- Go: `GOTOOLCHAIN=local` is written into `/usr/lib/go-1.24/go.env` (the toolchain's own
  defaults file), so Go never auto-downloads a toolchain from the proxy. `GOPROXY`, `GOSUMDB`
  and `GOFLAGS` are untouched (`GOFLAGS=-mod=mod` is not justified).
- .NET: `/usr/local/bin/dotnet` is a 3-line wrapper exporting `DOTNET_CLI_TELEMETRY_OPTOUT=1`,
  `DOTNET_NOLOGO=1`, `DOTNET_GENERATE_ASPNET_CERTIFICATE=false`, then exec-ing
  `/usr/share/dotnet/dotnet`. Anything calling the real binary by absolute path bypasses it.
- Composer: no telemetry; `COMPOSER_ALLOW_SUPERUSER` is irrelevant for UID 1000.

The image does **not** preseed any registry, package cache, NuGet source, Composer
repository or Go module cache, and adds no proxy settings.

## Build

Same base digest as mvp1 (`python:3.12.12-slim`, recorded in
`docs/archive/reviews/MVP_1_IMPLEMENTATION.md`):

```bash
tar -C fixtures/development -cf - Dockerfile .dockerignore | docker build \
  --build-arg PYTHON_IMAGE=python@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c \
  --build-arg CODEX_VERSION=0.169.0 -t principiis-development:mvp2-toolchains -
```

Result: `sha256:90dd9b4c3aa0a302ae4ff0eb410968e07f99c1cd9cc1c8824329e955a3961e98`
(local only, never pushed). The build took roughly 15 minutes on a contended host, almost
all of it the unchanged first layer. That layer was rebuilt (no cache was shared with mvp1)
and Debian had meanwhile published point updates, so its package patch levels are newer than
in mvp1 (for example Node 20.19.2, git 2.47.3, curl 8.14.1, bubblewrap 0.12.0 here; mvp1's
exact patch levels were not re-recorded). Codex 0.169.0, Python 3.12.12, Flask 3.1.3 and
SQLite 3.46.1 match mvp1. So "only the toolchains changed" holds for the recipe, not
byte-for-byte for the base layer.

### Size

| Image | Size | Layer |
| --- | --- | --- |
| mvp1 | 1,179,256,677 B (1.18 GB) | |
| mvp2-toolchains | 2,112,066,240 B (2.11 GB) | +933 MB |

Layers added: Debian PHP/Composer/Go 288 MB, .NET SDK 645 MB. The unchanged first layer was
1.06 GB. Apt lists are removed and the tarball deleted; no further trimming was tried (the
SDK's targeting packs are what make offline builds work).

## Model-free verification (2026-11-27, local Docker, no model, no credentials)

Versions (`--network none`, as UID 1000): `codex-cli 0.169.0`, `Python 3.12.12`, Flask 3.1.3,
SQLite 3.46.1, `go version go1.24.4 linux/amd64`, `dotnet --version` `10.0.404`,
`Composer version 2.8.8 2025-04-04`, `PHP 8.4.28 (cli)`, Node v20.19.2, npm 9.2.0,
git 2.47.3, bubblewrap 0.12.0. Image `Config.User` `1000:1000`, WorkingDir `/workspace`,
environment names unchanged from mvp1. PHP modules present: curl, mbstring, openssl, xml,
zip, json.

Offline smoke builds under the repo's restrictions (`restrictions(nested_sandbox=True)`:
read-only root, tmpfs `/home/developer` and `/tmp`, caps dropped, no-new-privileges,
repo seccomp profile, `--network none`):

- Go: `go mod init`, `go build`, run printed `hello from go`. A `go.mod` with `go 1.99`
  failed with `GOTOOLCHAIN=local`, i.e. no toolchain download is attempted.
- .NET: `dotnet new console` and `dotnet run` printed `Hello, World!` with the network off
  (restore succeeded from the SDK's bundled packs). `dotnet build --no-restore` right after
  `new --no-restore` fails as expected (no assets file). Each run prints
  "An issue was encountered verifying workloads", an offline workload-manifest check;
  harmless here.
- PHP/Composer: `composer install` and `dump-autoload` on a PSR-4 package with no
  dependencies, then a PHP script using the autoloader, `mb_strtoupper`, `curl_init`,
  `ZipArchive`, `DOMDocument` and openssl: all worked.
- Caches and config were created under the tmpfs home (`~/.cache`, `~/.composer`,
  `~/.config`, `~/.dotnet`, `~/.nuget`, `~/.templateengine`, `~/go`), about 33 MB after
  those runs. With `HOME` unset (`/`) Composer and Codex warn about unwritable paths; the
  runtime always sets `HOME=/home/developer`.
- bubblewrap (`--unshare-user --unshare-pid --unshare-net --ro-bind / /`): go, dotnet,
  composer and php run inside it; `go run` works; writes to `/usr` fail read-only.

Repo opt-in container controls against the new image ID
(`PO_RUNTIME_IMAGE=sha256:90dd9b4c...3961e98`):

- `test_development_runtime_containers.py`: `Ran 1 test in 20.808s ... OK` (real Codex
  workspace sandbox, user-local tool, network, effective container policy; evidence
  `/var/tmp/principiis-live-runs/img75/runtime/sandbox-control-1642360b91284286b28628f4f95a8909`).
- `test_preview_containers.py -k retained_virtual`: `Ran 1 test in 36.102s ... OK`.

**Not verified:** anything needing the network (`composer require`, `go get`, `dotnet add
package`/NuGet restore of real packages, npm/pip are unchanged); behaviour under the egress
proxy and allowlist; the `test_preview_containers.py` HTTP control (needs `PO_PREVIEW_IMAGE`,
not run); Codex login or any model call; the full fake-Docker unit suite; Go modules
needing Go newer than 1.24.4; a second independent rebuild for reproducibility.

## Network allowlist consequences (not changed here)

The PR #78 allowlist deliberately excludes `proxy.golang.org`; the owner decided to widen it
only after measurement. Under enforcement, then:

- `go get` / `go mod download` fail (only vendored or standard-library programs build).
- `composer install` of Packagist packages usually fetches archives from GitHub
  (`api.github.com`, `codeload.github.com`), which cannot be allowed safely; installs may
  fail even though `repo.packagist.org` metadata resolves. Plain `composer install` with no
  dependencies works offline.
- NuGet restore needs `api.nuget.org` (and `*.nuget.org`); .NET programs without package
  references build offline.

These are expected measurement outcomes, not image defects.

## What adopting this image requires (not done here)

Adoption changes the runtime image identity, so it needs **re-qualification and owner
approval**; nothing below has been changed:

- New `image` ID in every runtime JSON (`sha256:848b6276...` -> candidate ID), preview
  configs, and `principiis-development:mvp1` tag references in docs and fixtures.
- Evaluator manifests / benchmark packages that pin `runtime_image`
  `sha256:848b6276...` (see `principiis/evaluation.py`, `snapshot.py`, `preview.py`,
  `pipeline.py`, `assessment.py`, `investigation.py` and the tests that mention the image
  id: `tests/test_snapshot.py`, `test_condition_cli.py`, `test_benchmark_package.py`,
  `test_checkpoint_pipeline.py`, `test_assessment_cli.py`, `test_evaluation_runtime_containers.py`).
  Retained snapshots/venvs are bound to the attested image and cannot be restored under
  another.
- `DEVELOPMENT_RUNTIME.md`: the recipe text lists only Python/Node/Git/compiler tools and the
  recorded image ID; update it and the toolchain-preflight list (Go, dotnet, composer, php
  are not probed by `SANDBOX_PROBE`, so qualification should add them). The image-environment
  allow-list needs no change, because no new ENV was added.
- The #75 measurement request (`fixtures/development/network_measurement_request.txt`,
  item 3) already says "if PHP and Composer, .NET, or Go are available", so it needs no
  change; run the measurement with this image so those ecosystems are actually exercised
  before the allowlist is fixed.
- The runtime-version string includes image identity, so existing runs cannot continue under
  it.

## Risks

- **Size**: +933 MB (2.11 GB total); slower pulls/loads, larger attack surface.
- **Supply chain**: unpinned Debian patch levels; .NET integrity relies on a same-origin
  hash; Codex is installed from npm at build time (pre-existing). The build ran with
  network access.
- **Unpinned apt layer drift** makes the base layer differ from mvp1 on rebuild; compare
  by image ID only.
- **.NET** bundles Microsoft's NuGet defaults (`api.nuget.org`) and Go defaults
  (`proxy.golang.org`, `sum.golang.org`): network-limited agents will see failures, not
  silent fallbacks, but allowlist choices there are the owner's.
- Go 1.24 is older than the current upstream line.

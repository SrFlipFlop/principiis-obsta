# Supply a resolved Python 3.12 registry reference@sha256:digest; never a floating base.
ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}
ARG CODEX_VERSION=0.169.0
RUN apt-get update && apt-get install -y --no-install-recommends \
      nodejs npm git curl ca-certificates build-essential bubblewrap procps \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g "@openai/codex@${CODEX_VERSION}" \
    && npm cache clean --force \
    && python -m pip install --no-cache-dir 'Flask>=3.1,<3.2' \
    && mkdir -p /workspace /home/developer \
    && chmod 1777 /workspace \
    && codex --version \
    && python -c 'import flask, sqlite3, venv'
# Toolchains for the five package ecosystems (#75). Debian packages: PHP/Composer and Go;
# the official .NET SDK tarball is verified against the SHA-512 Microsoft publishes.
# Nothing here preseeds a registry or package cache. Environment settings that would need
# new image ENV names are carried by go.env and a wrapper instead, so the reviewed
# image-environment allow-list is unchanged.
ARG DOTNET_SDK_VERSION=10.0.404
ARG DOTNET_SDK_SHA512=577d0eb17fec33d029104c5c63a1ab0accc3e28776274abef2218dbac5af18d2109b5406d26b31d76f5c245215e3ba0926a94c20246c672c41847c9e1eb1dc50
RUN apt-get update && apt-get install -y --no-install-recommends \
      php-cli php-mbstring php-xml php-curl php-zip unzip composer golang-go \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i 's/^GOTOOLCHAIN=.*/GOTOOLCHAIN=local/' /usr/lib/go-1.24/go.env \
    && grep -qx 'GOTOOLCHAIN=local' /usr/lib/go-1.24/go.env \
    && go version | grep -q ' go1\.24\.' \
    && composer --version | grep -q 'Composer version 2\.' \
    && php -v | grep -q '^PHP 8\.4\.'
RUN curl -fsSL -o /tmp/dotnet-sdk.tar.gz \
      "https://builds.dotnet.microsoft.com/dotnet/Sdk/${DOTNET_SDK_VERSION}/dotnet-sdk-${DOTNET_SDK_VERSION}-linux-x64.tar.gz" \
    && echo "${DOTNET_SDK_SHA512}  /tmp/dotnet-sdk.tar.gz" | sha512sum -c - \
    && mkdir -p /usr/share/dotnet \
    && tar -xzf /tmp/dotnet-sdk.tar.gz -C /usr/share/dotnet \
    && rm /tmp/dotnet-sdk.tar.gz \
    && printf '%s\n' '#!/bin/sh' \
         'export DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1 DOTNET_GENERATE_ASPNET_CERTIFICATE=false' \
         'exec /usr/share/dotnet/dotnet "$@"' > /usr/local/bin/dotnet \
    && chmod 0755 /usr/local/bin/dotnet \
    && test "$(dotnet --version)" = "${DOTNET_SDK_VERSION}"
WORKDIR /workspace
USER 1000:1000
CMD ["python", "app.py"]

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
WORKDIR /workspace
USER 1000:1000
CMD ["python", "app.py"]

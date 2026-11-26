"""Credential redaction for retained Codex runtime logs."""
import re


def redact(value):
    """Remove recognizable credential fields without reading credential stores."""
    value = re.sub(r'(?i)("(?:api_key|access_token|refresh_token|id_token|authorization|password)"\s*:\s*)"[^"\n]*"', r'\1"[REDACTED]"', value)
    value = re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/-]+', r'\1[REDACTED]', value)
    return re.sub(r'\bsk-[A-Za-z0-9_-]+', '[REDACTED]', value)

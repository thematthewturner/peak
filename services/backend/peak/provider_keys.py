"""Server-side Claude API key lookup and the failure type shared by the model-calling code."""

import os
from pathlib import Path


class ProviderFailure(Exception):
    def __init__(self, message="The model service is unavailable; retry shortly", retryable=True):
        super().__init__(message)
        self.retryable = retryable


def key_for(provider="anthropic"):
    """Return the Claude API key from ANTHROPIC_API_KEY_FILE or ANTHROPIC_API_KEY."""
    if provider != "anthropic":
        raise ProviderFailure("Only Claude is supported", False)
    filename = os.getenv("ANTHROPIC_API_KEY_FILE")
    key = Path(filename).read_text().strip() if filename else os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise ProviderFailure("A server-side Claude API key is required", False)
    return key

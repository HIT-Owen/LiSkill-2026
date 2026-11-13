"""Minimal LLM access layer.

Three models appear in the paper, each reached through an OpenAI-compatible
chat-completions endpoint.  They are *not* interchangeable, so each paper stage
has its own constructor and its own environment prefix:

* **§3.3.3 licence reading, §3.4.1 term database** — Qwen3.5-9B carrying the LoRA
  adapter, served locally: :meth:`LLMConfig.from_env` (``LISKILL_LLM_*``).
* **§3.2.2 declaration normalisation** — the *base* Qwen3.5-9B, also served
  locally: :meth:`LLMConfig.for_normalization` (``LISKILL_NORMALIZE_*``).  A
  vLLM server exposing both the base model and the adapter answers both stages
  on one endpoint.
* **§3.3.2 pre-annotation, §4.4.2 workflow generation** — DeepSeek-V4-Flash-0731,
  the hosted general model that drafts labels and composes requirements into
  activation chains: :meth:`LLMConfig.for_drafting` (``LISKILL_DRAFT_*``).
  §4.1.4 runs it at ``reasoning effort = high`` with the vendor's default
  decoding parameters.

:class:`LLMConfig` itself names the *fine-tuned* model rather than the base
checkpoint: :func:`liskill.understand.train_lora.train` writes the adapter to
``out/qwen3.5-9b-liskill-lora``, and the server has to expose it under the name
the client asks for::

    vllm serve Qwen/Qwen3.5-9B --enable-lora \\
        --lora-modules Qwen3.5-9B-LiSkill=out/qwen3.5-9b-liskill-lora

Both ends are overridable through the environment without touching code::

    export LISKILL_LLM_BASE_URL=http://127.0.0.1:8000/v1
    export LISKILL_LLM_MODEL=Qwen3.5-9B-LiSkill

The client is optional: every module that needs a model accepts ``llm=None`` and
falls back to the deterministic implementations, which is how the released demo
runs offline.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LLMConfig:
    """The §3.3.3 understanding model: LoRA-adapted Qwen3.5-9B, served locally."""

    base_url: str = "http://127.0.0.1:8000/v1"
    model: str = "Qwen3.5-9B-LiSkill"
    api_key: str = ""
    #: ``None`` leaves sampling at the server default (§4.1.4 for the drafting pass)
    temperature: Optional[float] = 0.0
    #: DeepSeek reasoning budget; only sent when set
    reasoning_effort: Optional[str] = None
    max_tokens: int = 1024
    timeout: int = 120
    retries: int = 2

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            base_url=os.environ.get("LISKILL_LLM_BASE_URL", cls.base_url),
            model=os.environ.get("LISKILL_LLM_MODEL", cls.model),
            api_key=os.environ.get("LISKILL_LLM_API_KEY", ""),
            temperature=float(os.environ.get("LISKILL_LLM_TEMPERATURE", "0")),
            max_tokens=int(os.environ.get("LISKILL_LLM_MAX_TOKENS", "1024")),
        )

    @classmethod
    def for_drafting(cls) -> "LLMConfig":
        """§3.3.2 pre-annotation and §4.4.2 requirement-driven workflow generation.

        The general-purpose model: it never reads licence text inside the
        framework, it only drafts labels and composes agent workflows.  §4.1.4
        runs this pass with ``reasoning effort = high`` and the vendor's default
        decoding parameters, so temperature is left unset.
        """
        return cls(
            base_url=os.environ.get("LISKILL_DRAFT_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.environ.get("LISKILL_DRAFT_MODEL", "DeepSeek-V4-Flash-0731"),
            api_key=os.environ.get("LISKILL_DRAFT_API_KEY", ""),
            temperature=None,
            reasoning_effort=os.environ.get("LISKILL_DRAFT_REASONING_EFFORT", "high"),
            max_tokens=int(os.environ.get("LISKILL_DRAFT_MAX_TOKENS", "1024")),
        )

    @classmethod
    def for_normalization(cls) -> "LLMConfig":
        """§3.2.2 — the base Qwen3.5-9B, served locally, maps declarations.

        The base checkpoint, not the §3.3.3 adapter: normalisation asks the model
        to pick from a closed candidate set, which needs no fine-tuning.  A vLLM
        server exposing both names answers both stages on the same endpoint.
        """
        return cls(
            base_url=os.environ.get("LISKILL_NORMALIZE_BASE_URL", cls.base_url),
            model=os.environ.get("LISKILL_NORMALIZE_MODEL", "Qwen3.5-9B"),
            api_key=os.environ.get("LISKILL_NORMALIZE_API_KEY", ""),
            temperature=float(os.environ.get("LISKILL_NORMALIZE_TEMPERATURE", "0")),
            max_tokens=int(os.environ.get("LISKILL_NORMALIZE_MAX_TOKENS", "1024")),
        )


class OpenAICompatClient:
    """Tiny chat-completions client on top of ``urllib`` (no extra dependency)."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or LLMConfig.from_env()

    def complete(self, prompt: str, json_mode: bool = False, system: str = "") -> str:
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
        }
        # omitted -> the endpoint applies its own default (§4.1.4)
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.reasoning_effort:
            payload["reasoning_effort"] = self.config.reasoning_effort
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error: Optional[Exception] = None
        for attempt in range(self.config.retries + 1):
            try:
                return self._post(payload)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"LLM request failed: {last_error}")

    def _post(self, payload: Dict[str, Any]) -> str:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key or 'EMPTY'}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]

"""Claude-backed mission assistant: a manual tool-use loop over read-only tools.

Disabled (``503 assistant_disabled``) until ``ANTHROPIC_API_KEY`` is set in ``.env`` or the
environment and the backend is restarted. Request shape follows the Anthropic Python SDK docs:

* model configurable (``MARS_ASSISTANT_MODEL``, default ``claude-opus-5-5``);
* thinking is adaptive / always on for Opus 5.5; depth set explicitly with
  ``output_config.effort`` (``MARS_ASSISTANT_EFFORT``, default ``medium``);
* tool choice left at ``auto`` (forced tool choice is rejected by current models);
* the stable system prompt is marked for prompt caching (tools + system form the cached prefix);
* server-side refusal fallbacks (beta ``server-side-fallback-2026-07-01``, ``fallbacks:
  "default"``) unless disabled or the model is a Haiku model (which has none);
* ``stop_reason == "refusal"`` is reported, never treated as an answer.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

import anthropic
from sqlalchemy.engine import Engine
from sqlmodel import Session

from mars_explorer.assistant.prompts import CONTEXT_PREFIX, SYSTEM_PROMPT
from mars_explorer.assistant.tools import TOOLS, ToolContext, run_tool
from mars_explorer.core.config import Settings
from mars_explorer.core.errors import AppError
from mars_explorer.terrain.service import TerrainService

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
REQUEST_TIMEOUT_S = 120.0

ClientFactory = Callable[[str], anthropic.Anthropic]


class AssistantDisabledError(AppError):
    status_code = 503
    code = "assistant_disabled"


class AssistantUpstreamError(AppError):
    status_code = 502
    code = "assistant_upstream_error"


@dataclass(frozen=True, slots=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


@dataclass(slots=True)
class ToolCallRecord:
    name: str
    input: dict[str, Any]
    is_error: bool
    result_chars: int


@dataclass(slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def add(self, usage: Any) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_read_input_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.cache_creation_input_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0


@dataclass(slots=True)
class ChatResult:
    reply: str
    model: str
    stop_reason: str | None
    refused: bool
    fallback_used: bool
    rounds: int
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    notes: list[str] = field(default_factory=list)


def default_client_factory(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, timeout=REQUEST_TIMEOUT_S, max_retries=2)


class AssistantService:
    def __init__(
        self,
        settings: Settings,
        engine: Engine,
        terrain: TerrainService | None = None,
        client_factory: ClientFactory = default_client_factory,
    ) -> None:
        self._settings = settings
        self._engine = engine
        self._terrain = terrain
        self._client_factory = client_factory
        self._client: anthropic.Anthropic | None = None

    # ---- status ------------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return self._settings.anthropic_api_key is not None

    @property
    def model(self) -> str:
        return self._settings.assistant_model

    @property
    def fallbacks_active(self) -> bool:
        return self._settings.assistant_fallbacks and "haiku" not in self.model

    def _get_client(self) -> anthropic.Anthropic:
        key = self._settings.anthropic_api_key
        if key is None:
            raise AssistantDisabledError(
                "The AI assistant is not configured. Add ANTHROPIC_API_KEY=<your key> to the .env "
                "file in the project root and restart the backend."
            )
        if self._client is None:
            self._client = self._client_factory(key.get_secret_value())
        return self._client

    # ---- chat --------------------------------------------------------------------------

    def _request(self, client: anthropic.Anthropic, messages: list[dict[str, Any]]) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self._settings.assistant_max_tokens,
            "system": [
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            "tools": [t.definition() for t in TOOLS],
            "messages": messages,
            "output_config": {"effort": self._settings.assistant_effort},
        }
        try:
            if self.fallbacks_active:
                return client.beta.messages.create(
                    betas=[FALLBACK_BETA], fallbacks="default", **kwargs
                )
            return client.messages.create(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise AssistantUpstreamError(
                "The Anthropic API rejected the API key (401). Check ANTHROPIC_API_KEY in .env.",
                code="assistant_auth_failed",
            ) from exc
        except anthropic.PermissionDeniedError as exc:
            raise AssistantUpstreamError(
                "The API key is not allowed to use this model (403).",
                code="assistant_permission_denied",
            ) from exc
        except anthropic.NotFoundError as exc:
            raise AssistantUpstreamError(
                f"Model {self.model!r} was not found (404). Check MARS_ASSISTANT_MODEL.",
                code="assistant_model_not_found",
            ) from exc
        except anthropic.RateLimitError as exc:
            raise AssistantUpstreamError(
                "Rate limited by the Anthropic API (429). Wait a moment and try again.",
                code="assistant_rate_limited",
                status_code=429,
            ) from exc
        except anthropic.BadRequestError as exc:
            raise AssistantUpstreamError(
                f"The Anthropic API rejected the request (400): {exc.message}",
                code="assistant_bad_request",
            ) from exc
        except anthropic.APIStatusError as exc:
            raise AssistantUpstreamError(
                f"Anthropic API error ({exc.status_code}). Try again later."
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise AssistantUpstreamError(
                "Could not reach the Anthropic API (network error or timeout).",
                code="assistant_unreachable",
            ) from exc

    def chat(self, history: Sequence[ChatTurn], context: str | None = None) -> ChatResult:
        """Answer the last user turn of ``history`` (client-held conversation, text only)."""
        if not history or history[-1].role != "user":
            raise AppError("The conversation must end with a user message.", code="invalid_request")
        client = self._get_client()
        messages: list[dict[str, Any]] = [
            {"role": t.role, "content": t.content} for t in history if t.content.strip()
        ]
        if context:
            messages[-1] = {
                "role": "user",
                "content": CONTEXT_PREFIX.format(context=context[:300]) + messages[-1]["content"],
            }

        result = ChatResult(
            reply="",
            model=self.model,
            stop_reason=None,
            refused=False,
            fallback_used=False,
            rounds=0,
        )
        max_rounds = self._settings.assistant_max_tool_rounds
        response: Any = None
        with Session(self._engine) as session:
            ctx = ToolContext(session=session, terrain=self._terrain)
            while True:
                response = self._request(client, messages)
                result.rounds += 1
                result.usage.add(response.usage)
                result.model = response.model
                result.stop_reason = response.stop_reason
                if any(getattr(b, "type", None) == "fallback" for b in response.content) or any(
                    getattr(i, "type", None) == "fallback_message"
                    for i in (getattr(response.usage, "iterations", None) or [])
                ):
                    result.fallback_used = True

                if response.stop_reason == "refusal":
                    result.refused = True
                    details = getattr(response, "stop_details", None)
                    category = getattr(details, "category", None)
                    log.info("assistant refusal (category=%s)", category)
                    result.reply = (
                        "The model declined to answer this request"
                        + (f" (category: {category})." if category else ".")
                        + " Try rephrasing the question."
                    )
                    return result

                if response.stop_reason == "pause_turn":
                    messages.append({"role": "assistant", "content": response.content})
                    continue

                if response.stop_reason != "tool_use":
                    break

                if result.rounds > max_rounds:
                    result.notes.append(
                        f"Stopped after {max_rounds} tool rounds; the answer may be incomplete."
                    )
                    break

                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if getattr(block, "type", None) != "tool_use":
                        continue
                    args = block.input if isinstance(block.input, dict) else {}
                    text, is_error = run_tool(ctx, block.name, args)
                    result.tool_calls.append(ToolCallRecord(block.name, args, is_error, len(text)))
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": text,
                            **({"is_error": True} if is_error else {}),
                        }
                    )
                messages.append({"role": "user", "content": tool_results})

        result.reply = "\n\n".join(
            b.text for b in response.content if getattr(b, "type", None) == "text" and b.text
        ).strip()
        if response.stop_reason == "max_tokens":
            result.notes.append("The answer was cut off at the output token limit.")
        if not result.reply:
            result.reply = "(The model returned no text. Try asking again.)"
        return result

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "model": self.model,
            "effort": self._settings.assistant_effort,
            "fallbacks": self.fallbacks_active,
            "max_tool_rounds": self._settings.assistant_max_tool_rounds,
            "tools": [{"name": t.name, "description": t.description} for t in TOOLS],
        }

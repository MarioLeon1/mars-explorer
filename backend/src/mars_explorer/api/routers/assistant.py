"""Optional AI mission assistant (read-only tools; disabled without ANTHROPIC_API_KEY)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Request

from mars_explorer.api import schemas
from mars_explorer.assistant.service import AssistantService, ChatTurn
from mars_explorer.core.provenance import Provenance

router = APIRouter(prefix="/assistant", tags=["assistant"])

HOW_TO_ENABLE = [
    "Create an API key at https://platform.claude.com (Settings -> API keys). API usage is "
    "billed separately from a Claude.ai subscription.",
    "Open the .env file in the project root and add a line: ANTHROPIC_API_KEY=<your key>",
    "Optional: choose a cheaper model with MARS_ASSISTANT_MODEL=claude-haiku-5-5",
    r"Restart the backend (close and re-run .\scripts\dev.ps1).",
]
DATA_SENT = [
    "Your questions and the visible conversation.",
    "Results of the read-only tools the model calls: metadata of public NASA images, real "
    "drives and localizations, perception statistics and terrain status.",
    "Requests go to the Anthropic API; nothing else from your computer is sent.",
]
NEVER = [
    "No images or files are uploaded.",
    "The assistant cannot plan routes, drive anything, download data or change settings.",
    "The key stays in .env on your machine (gitignored) and is never sent to the browser.",
]
PRICING = [
    schemas.ModelPrice(
        model="claude-opus-5-5",
        input_usd_per_mtok=4.0,
        output_usd_per_mtok=20.0,
        note="Default: most capable.",
    ),
    schemas.ModelPrice(
        model="claude-sonnet-5-5",
        input_usd_per_mtok=2.0,
        output_usd_per_mtok=10.0,
        note="Balanced cost and quality.",
    ),
    schemas.ModelPrice(
        model="claude-haiku-5-5",
        input_usd_per_mtok=0.10,
        output_usd_per_mtok=0.50,
        note="Cheapest; fine for simple lookups.",
    ),
]


def _svc(request: Request) -> AssistantService:
    return request.app.state.assistant


@router.get("/status", response_model=schemas.AssistantStatusOut)
def status(request: Request) -> schemas.AssistantStatusOut:
    info = _svc(request).status()
    return schemas.AssistantStatusOut(
        **info,
        how_to_enable=HOW_TO_ENABLE,
        data_sent=DATA_SENT,
        never=NEVER,
        pricing=PRICING,
    )


def _context_text(context: schemas.ChatContextIn | None) -> str | None:
    if context is None:
        return None
    parts = []
    if context.page:
        parts.append(f"page {context.page}")
    if context.sol is not None:
        parts.append(f"sol {context.sol}")
    if context.image_id:
        parts.append(f"image {context.image_id}")
    return ", ".join(parts) or None


@router.post("/chat", response_model=schemas.ChatResponse)
def chat(request: Request, body: schemas.ChatRequest) -> schemas.ChatResponse:
    result = _svc(request).chat(
        [ChatTurn(m.role, m.content) for m in body.messages], _context_text(body.context)
    )
    return schemas.ChatResponse(
        reply=result.reply,
        model=result.model,
        stop_reason=result.stop_reason,
        refused=result.refused,
        fallback_used=result.fallback_used,
        rounds=result.rounds,
        tool_calls=[schemas.ToolCallOut(**asdict(c)) for c in result.tool_calls],
        usage=schemas.UsageOut(**asdict(result.usage)),
        notes=result.notes,
        provenance=Provenance.DERIVED,
    )

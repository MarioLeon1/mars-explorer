"""AI assistant (contract v1.4): disabled without a key; with a key, a read-only tool loop.

The real Anthropic SDK is used with a mocked HTTP transport (``httpx2.MockTransport``; the SDK is
built on httpx2), so the exact request bodies and headers sent to the API are asserted. No
network, no real key.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import anthropic
import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient

from mars_explorer.api.app import create_app
from mars_explorer.assistant.tools import TOOLS, ToolContext, run_tool
from mars_explorer.core.config import Settings
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.service import ImageSelection, IngestService
from tests.conftest import FakeNasa

Reply = dict[str, Any] | Callable[[dict[str, Any]], httpx2.Response]


class FakeAnthropic:
    """Scripted Messages API: returns the queued responses in order, recording each request."""

    def __init__(self, replies: list[Reply]) -> None:
        self.replies = list(replies)
        self.requests: list[httpx2.Request] = []
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        body = json.loads(request.content)
        self.bodies.append(body)
        reply = self.replies.pop(0)
        if callable(reply):
            return reply(body)
        return httpx2.Response(200, json=reply)

    def factory(self, api_key: str) -> anthropic.Anthropic:
        assert api_key == "sk-ant-test"
        return anthropic.Anthropic(
            api_key=api_key,
            max_retries=0,
            http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(self)),
        )


def message(content: list[dict[str, Any]], stop_reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": extra.pop("model", "claude-opus-5-5"),
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 50},
        **extra,
    }


def tool_use(name: str, args: dict[str, Any], tool_id: str = "toolu_1") -> dict[str, Any]:
    return {"type": "tool_use", "id": tool_id, "name": name, "input": args}


def text(value: str) -> dict[str, Any]:
    return {"type": "text", "text": value}


@pytest.fixture
def seeded(settings: Settings, fake_nasa: FakeNasa) -> Settings:
    engine = make_engine(settings.database_path)
    with httpx.Client(transport=httpx.MockTransport(fake_nasa)) as http:
        service = IngestService(engine, settings, http, sleep=lambda _: None)
        service.ingest_images([ImageSelection(sol_min=0, sol_max=5000)], sizes=())
        service.ingest_waypoints()
        service.ingest_traverse()
    engine.dispose()
    return settings


@contextmanager
def make_client(
    settings: Settings, fake_nasa: FakeNasa, fake: FakeAnthropic, **overrides: Any
) -> Iterator[TestClient]:
    configured = settings.model_copy(update={"anthropic_api_key": "sk-ant-test", **overrides})
    configured = Settings.model_validate(configured.model_dump())  # re-validate the SecretStr
    app = create_app(
        configured,
        transport=httpx.MockTransport(fake_nasa),
        assistant_client_factory=fake.factory,
    )
    with TestClient(app) as client:
        yield client


def ask(client: TestClient, question: str = "Where is the rover?", **extra: Any) -> Any:
    return client.post(
        "/api/assistant/chat", json={"messages": [{"role": "user", "content": question}], **extra}
    )


# ---- disabled (no key) ---------------------------------------------------------------------


def test_status_without_key_explains_how_to_enable(client: TestClient) -> None:
    body = client.get("/api/assistant/status").json()
    assert body["enabled"] is False
    assert body["model"] == "claude-opus-5-5"
    assert any("ANTHROPIC_API_KEY" in step for step in body["how_to_enable"])
    assert {p["model"] for p in body["pricing"]} >= {"claude-opus-5-5", "claude-haiku-5-5"}
    assert {t["name"] for t in body["tools"]} == {t.name for t in TOOLS}
    assert any("cannot plan routes" in n for n in body["never"])


def test_chat_without_key_is_503_assistant_disabled(client: TestClient) -> None:
    response = ask(client)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "assistant_disabled"
    assert "ANTHROPIC_API_KEY" in response.json()["error"]["message"]


# ---- enabled (mocked API) ------------------------------------------------------------------


def test_tool_loop_request_shape_and_answer(seeded: Settings, fake_nasa: FakeNasa) -> None:
    fake = FakeAnthropic(
        [
            message([tool_use("get_rover_position", {})], "tool_use"),
            message([text("The latest localization is from sol 2024.")], "end_turn"),
        ]
    )
    with make_client(seeded, fake_nasa, fake) as client:
        assert client.get("/api/assistant/status").json()["enabled"] is True
        response = ask(client, context={"page": "replay", "sol": 2024})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reply"] == "The latest localization is from sol 2024."
    assert body["label"] == "ai_generated" and body["provenance"] == "derived"
    assert body["rounds"] == 2
    assert body["tool_calls"] == [
        {
            "name": "get_rover_position",
            "input": {},
            "is_error": False,
            "result_chars": body["tool_calls"][0]["result_chars"],
        }
    ]
    assert body["usage"]["input_tokens"] == 200 and body["usage"]["cache_read_input_tokens"] == 100

    first, second = fake.bodies
    request = fake.requests[0]
    assert "server-side-fallback-2026-07-01" in request.headers["anthropic-beta"]
    assert first["fallbacks"] == "default"
    assert first["model"] == "claude-opus-5-5"
    assert first["output_config"] == {"effort": "medium"}
    assert first["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "tool_choice" not in first  # auto: forcing a tool is rejected by current models
    assert "thinking" not in first  # Opus 5.5: adaptive thinking is always on
    assert [t["name"] for t in first["tools"]] == [t.name for t in TOOLS]
    assert first["messages"][0]["content"].startswith("[App context")
    assert "sol 2024" in first["messages"][0]["content"]
    # Second round: assistant tool_use echoed back, then the tool result.
    assert second["messages"][1]["content"][0]["type"] == "tool_use"
    result = second["messages"][2]["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "toolu_1"
    position = json.loads(result["content"])
    assert position["available"] is True and position["provenance"] == "real_observation"
    assert any("no public real-time telemetry" in c for c in position["caveats"])


def test_refusal_is_reported_not_answered(settings: Settings, fake_nasa: FakeNasa) -> None:
    fake = FakeAnthropic(
        [message([], "refusal", stop_details={"type": "refusal", "category": "cyber"})]
    )
    with make_client(settings, fake_nasa, fake) as client:
        body = ask(client).json()
    assert body["refused"] is True
    assert "declined" in body["reply"] and "cyber" in body["reply"]


def test_fallback_usage_is_detected(settings: Settings, fake_nasa: FakeNasa) -> None:
    fake = FakeAnthropic(
        [
            message(
                [
                    {
                        "type": "fallback",
                        "from": {"model": "claude-opus-5-5"},
                        "to": {"model": "claude-opus-5"},
                    },
                    text("Answer from the fallback model."),
                ],
                "end_turn",
                model="claude-opus-5",
            )
        ]
    )
    with make_client(settings, fake_nasa, fake) as client:
        body = ask(client).json()
    assert body["fallback_used"] is True
    assert body["model"] == "claude-opus-5"
    assert body["reply"] == "Answer from the fallback model."


def test_haiku_model_skips_fallbacks(settings: Settings, fake_nasa: FakeNasa) -> None:
    fake = FakeAnthropic([message([text("ok")], "end_turn", model="claude-haiku-5-5")])
    with make_client(
        settings, fake_nasa, fake, assistant_model="claude-haiku-5-5", assistant_effort="low"
    ) as client:
        assert client.get("/api/assistant/status").json()["fallbacks"] is False
        assert ask(client).status_code == 200
    assert "fallbacks" not in fake.bodies[0]
    assert "server-side-fallback" not in fake.requests[0].headers.get("anthropic-beta", "")
    assert fake.bodies[0]["output_config"] == {"effort": "low"}


def test_bad_tool_input_goes_back_as_error_result(seeded: Settings, fake_nasa: FakeNasa) -> None:
    fake = FakeAnthropic(
        [
            message([tool_use("search_images", {"camera": "TELESCOPE"})], "tool_use"),
            message([tool_use("plan_route", {}, "toolu_2")], "tool_use"),
            message([text("Sorry, that camera does not exist.")], "end_turn"),
        ]
    )
    with make_client(seeded, fake_nasa, fake) as client:
        body = ask(client).json()
    assert [c["is_error"] for c in body["tool_calls"]] == [True, True]
    first_result = fake.bodies[1]["messages"][2]["content"][0]
    assert first_result["is_error"] is True and "unknown camera" in first_result["content"]
    second_result = fake.bodies[2]["messages"][4]["content"][0]
    assert "unknown tool" in second_result["content"]


def test_tool_round_limit_stops_the_loop(settings: Settings, fake_nasa: FakeNasa) -> None:
    loop = [message([tool_use("get_mission_overview", {}, f"t{i}")], "tool_use") for i in range(3)]
    fake = FakeAnthropic(loop)
    with make_client(settings, fake_nasa, fake, assistant_max_tool_rounds=2) as client:
        body = ask(client).json()
    assert body["rounds"] == 3
    assert any("tool rounds" in n for n in body["notes"])


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "assistant_auth_failed"),
        (404, "assistant_model_not_found"),
        (429, "assistant_rate_limited"),
        (400, "assistant_bad_request"),
        (529, "assistant_upstream_error"),
    ],
)
def test_api_errors_map_to_clear_codes(
    settings: Settings, fake_nasa: FakeNasa, status: int, code: str
) -> None:
    def fail(_: dict[str, Any]) -> httpx2.Response:
        return httpx2.Response(
            status, json={"type": "error", "error": {"type": "x", "message": "nope"}}
        )

    fake = FakeAnthropic([fail])
    with make_client(settings, fake_nasa, fake) as client:
        response = ask(client)
    assert response.json()["error"]["code"] == code
    assert response.status_code == (429 if status == 429 else 502)


def test_conversation_must_end_with_user(settings: Settings, fake_nasa: FakeNasa) -> None:
    fake = FakeAnthropic([])
    with make_client(settings, fake_nasa, fake) as client:
        response = client.post(
            "/api/assistant/chat",
            json={
                "messages": [
                    {"role": "user", "content": "hi"},
                    {"role": "assistant", "content": "hello"},
                ]
            },
        )
        empty = client.post("/api/assistant/chat", json={"messages": []})
    assert response.status_code == 400
    assert empty.status_code == 422
    assert fake.requests == []


# ---- tools are read-only and work on real data ---------------------------------------------

SAMPLE_ARGS: dict[str, dict[str, Any]] = {
    "search_images": {"sol": 2024, "camera": "NAVCAM_LEFT", "limit": 3},
    "get_image_details": {"image_id": "missing"},
    "get_drives": {"sol_min": 1100, "sol_max": 1200},
    "get_sol_summary": {"sol": 2024},
    "list_sequences": {"sol": 2024},
}


def test_every_tool_runs_on_seeded_data_without_writing(seeded: Settings) -> None:
    from sqlmodel import Session

    engine = make_engine(seeded.database_path)
    before = (seeded.database_path.stat().st_mtime_ns, seeded.database_path.stat().st_size)
    with Session(engine) as session:
        ctx = ToolContext(session=session, terrain=None)
        for tool in TOOLS:
            output, is_error = run_tool(ctx, tool.name, SAMPLE_ARGS.get(tool.name, {}))
            assert not is_error, (tool.name, output)
            json.loads(output)
        images = json.loads(run_tool(ctx, "search_images", SAMPLE_ARGS["search_images"])[0])
        assert images["returned"] == 3 and images["provenance"] == "real_observation"
        detail = json.loads(
            run_tool(ctx, "get_image_details", {"image_id": images["images"][0]["image_id"]})[0]
        )
        assert detail["found"] is True and "uncalibrated" in detail["product_note"]
        drives = json.loads(run_tool(ctx, "get_drives", SAMPLE_ARGS["get_drives"])[0])
        assert drives["count"] == 3
        assert run_tool(ctx, "get_drives", {"sol_min": 5, "sol_max": 1})[1] is True
        assert run_tool(ctx, "get_sol_summary", {"sol": "x"})[1] is True
    engine.dispose()
    after = (seeded.database_path.stat().st_mtime_ns, seeded.database_path.stat().st_size)
    assert after == before

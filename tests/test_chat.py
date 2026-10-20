from unittest.mock import patch, MagicMock

import requests

from app.llm import chat


FINANCIALS = {"monthly_surplus": 20000, "net_monthly_income": 80000, "total_monthly_expenses": 60000}


def _sse_response(lines):
    resp = MagicMock()
    resp.__enter__.return_value = resp
    resp.iter_lines.return_value = iter(lines)
    return resp


@patch("app.llm.chat.requests.post")
def test_stream_chat_parses_openai_compatible_sse(mock_post):
    mock_post.return_value = _sse_response([
        'data: {"choices":[{"delta":{"role":"assistant"}}]}',
        "",
        'data: {"choices":[{"delta":{"content":"Your surplus is "}}]}',
        'data: {"choices":[{"delta":{"content":"₹20,000."}}]}',
        "data: [DONE]",
    ])

    out = "".join(chat.stream_chat("How much can I save?", [], FINANCIALS))

    assert out == "Your surplus is ₹20,000."
    payload = mock_post.call_args.kwargs["json"]
    assert payload["stream"] is True
    assert payload["messages"][0]["role"] == "system"
    assert "[CONTEXT]" in payload["messages"][-1]["content"]
    assert mock_post.call_args.args[0].endswith("/chat/completions")


@patch("app.llm.chat.requests.post")
def test_stream_chat_connection_error_is_graceful(mock_post):
    mock_post.side_effect = requests.ConnectionError("refused")
    out = "".join(chat.stream_chat("hi", [], FINANCIALS))
    assert "could not reach the LLM provider" in out


def test_hosted_provider_without_key_is_unconfigured(monkeypatch):
    monkeypatch.setattr(chat, "LLM_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(chat, "LLM_API_KEY", "")
    assert not chat.is_configured()
    assert "LLM_API_KEY not configured" in "".join(chat.stream_chat("hi", [], FINANCIALS))


def test_local_ollama_needs_no_key(monkeypatch):
    monkeypatch.setattr(chat, "LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(chat, "LLM_API_KEY", "")
    assert chat.is_configured()

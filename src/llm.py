"""Lightweight ChatOpenAI replacement.

Uses only Python stdlib (urllib, json) — no langchain dependencies.
Supports:
  - ChatOpenAI(model, base_url, api_key, temperature, extra_body, ...)
  - llm.bind_tools(tools) -> new LLM instance that injects tool schemas
  - llm.invoke(messages) -> AIMessage-like object with .content and .tool_calls
"""

import json
from js import fetch, Request, Headers
import inspect
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Response wrapper (duck-typed AIMessage)
# ---------------------------------------------------------------------------

class AIMessage:
    """Minimal AIMessage-compatible response object."""

    def __init__(self, content: str = "", tool_calls: list | None = None):
        self.content = content
        self.tool_calls = tool_calls or []

    def __repr__(self):
        return f"AIMessage(content={self.content!r}, tool_calls={self.tool_calls})"


# ---------------------------------------------------------------------------
# ChatOpenAI — lightweight OpenAI-compatible chat client
# ---------------------------------------------------------------------------

class ChatOpenAI:
    """Minimal OpenAI-compatible chat client (no langchain required).

    Parameters mirror the LangChain ChatOpenAI for easy drop-in replacement.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        temperature: float = 0.7,
        streaming: bool = False,
        extra_body: dict | None = None,
        tools: list | None = None,          # injected by bind_tools
        **kwargs,
    ):
        self.model = model
        # Normalise base_url: strip trailing slash, ensure no /chat/completions suffix
        self.base_url = base_url.rstrip("/")
        if self.base_url.endswith("/chat/completions"):
            self.base_url = self.base_url[: -len("/chat/completions")]
        self.api_key = api_key
        self.temperature = temperature
        self.streaming = streaming
        self.extra_body: dict = extra_body or {}
        self._tools: list = tools or []

    # ------------------------------------------------------------------
    # Tool binding
    # ------------------------------------------------------------------

    def bind_tools(self, tools: list) -> "ChatOpenAI":
        """Return a new ChatOpenAI with tool schemas bound."""
        return ChatOpenAI(
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=self.temperature,
            streaming=self.streaming,
            extra_body=dict(self.extra_body),
            tools=list(tools),
        )

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    async def ainvoke(self, messages: list[dict]) -> AIMessage:
        """Send messages to the chat API (async) and return an AIMessage."""
        payload = self._build_payload(messages)
        response_data = await self._post(payload)
        return self._parse_response(response_data)

    def invoke(self, messages: list[dict]) -> AIMessage:
        """Synchronous invoke - for CF Workers we primarily use ainvoke."""
        # This is a bit tricky since js.fetch is async. 
        # For simplicity in this env, we'll suggest ainvoke.
        raise RuntimeError("Use ainvoke instead of invoke in Cloudflare Workers")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_payload(self, messages: list[dict]) -> dict:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        if self._tools:
            payload["tools"] = [self._tool_schema(t) for t in self._tools]
            payload["tool_choice"] = "auto"

        # Merge extra_body at top level (e.g. {"real": "https://..."})
        payload.update(self.extra_body)

        return payload

    @staticmethod
    def _tool_schema(tool) -> dict:
        """Convert a StructuredTool / callable to OpenAI tool schema."""
        # StructuredTool from our local tool_decorator exposes .openai_schema
        if hasattr(tool, "openai_schema"):
            return {"type": "function", "function": tool.openai_schema}
        # Fallback: build minimal schema from __name__ / __doc__
        name = getattr(tool, "name", None) or getattr(tool, "__name__", "unknown")
        description = inspect.getdoc(tool) or ""
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {"type": "object", "properties": {}},
            },
        }

    async def _post(self, payload: dict) -> dict:
        url = f"{self.base_url}/chat/completions"
        
        headers = Headers.new()
        headers.set("Content-Type", "application/json")
        headers.set("Authorization", f"Bearer {self.api_key}")

        body = json.dumps(payload)
        req = Request.new(url, method="POST", body=body, headers=headers)
        
        # Cloudflare Workers environment: fetch is a promise
        resp = await fetch(req)
        if not resp.ok:
            error_text = await resp.text()
            raise RuntimeError(f"API Error ({resp.status}): {error_text}")
            
        # Parse JSON result
        data_js = await resp.json()
        return data_js.to_py()

    @staticmethod
    def _parse_response(data: dict) -> AIMessage:
        choice = data["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""

        raw_tool_calls = message.get("tool_calls") or []
        tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            args_raw = fn.get("arguments", "{}")
            try:
                args = json.loads(args_raw)
            except Exception:
                args = {}
            tool_calls.append({
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
                "args": args,
            })

        return AIMessage(content=content, tool_calls=tool_calls)

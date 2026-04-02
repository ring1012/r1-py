"""LangChain + Cloudflare Python Worker Example.

This example demonstrates how to use langchain-cloudflare with Python Workers,
using the Workers AI and Vectorize bindings directly for optimal performance.

Features demonstrated:
- Basic chat invocation
- Structured output with Pydantic models
- Tool calling
- Multi-turn conversations
- create_agent pattern with structured output and tools
- Vectorize operations (insert, search, delete)
- D1 database operations

All endpoints accept an optional "model" parameter in the request body to specify
which Workers AI model to use. Defaults to Qwen if not specified.
"""

from tools import ALL_TOOLS
from workers import Response, WorkerEntrypoint
from langchain_openai import ChatOpenAI


class Default(WorkerEntrypoint):
    """Main Worker entrypoint for LangChain examples."""

    # MARK: - Request Routing

    async def fetch(self, request, env):
        """Handle incoming HTTP requests."""
        try:
            url = request.url
            print(url)
            path = url.split("/")[-1].split("?")[0] if "/" in url else ""

            return await self.handle_tool_calling(request)

        except Exception as e:
            print(e)
            return Response.json(
                {"error": str(e), "type": type(e).__name__},
                status=500,
            )

    # MARK: - Tool Calling Handler

    async def handle_tool_calling(self, request):
        """Handle tool calling."""
        data = await request.json()
        message = data.get("message", "上海天气")
        model = data.get("model", "Qwen/Qwen3-8B")
        huan = await self.env.YOU.get("huan")
        print(huan)

        llm = ChatOpenAI(
            model=model,
            base_url="https://api-inference.modelscope.cn/v1",
            api_key="ms-3bff3ce4-c2b3-4dbe-911d-156ce266b729",
            temperature=0.0,
            streaming=False,
            extra_body={
                "enable_thinking": False
            }
        )
        llm_with_tools = llm.bind_tools(ALL_TOOLS)

        TOOL_MAP = {tool.name: tool for tool in ALL_TOOLS}

        response = llm_with_tools.invoke(message)

        if response.tool_calls:
            tc = response.tool_calls[0]  # ✅ 只处理一个

            tool = TOOL_MAP.get(tc["name"])
            result = tool.invoke(tc["args"]) if tool else "unknown tool"

            return Response.json({
                "role": "tool",
                "content": str(result),
                "tool_call_id": tc["id"],
            })
        return Response.json({
            "role": "tool",
            "text": response.text
        })

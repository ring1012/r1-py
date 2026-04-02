"""LangChain + Cloudflare Python Worker Example.

Features demonstrated:
- Custom endpoint routing
- KV retrieval for device-specific config
- Dynamic LLM and tool configuration
- Tool calling with device context
- Return structured responses for box-client
"""

import json
from tools import R1Tools
from workers import Response, WorkerEntrypoint
from llm import ChatOpenAI
from urllib.parse import urlparse, parse_qs


class Default(WorkerEntrypoint):
    """Main Worker entrypoint for LangChain examples."""

    # MARK: - Request Routing

    async def fetch(self, request, env):
        """Handle incoming HTTP requests."""
        try:
            url = urlparse(request.url)
            path = url.path
            
            # Handle /r1/ai/chat endpoint
            if path == "/r1/ai/chat":
                # Get user input from query string
                query_params = parse_qs(url.query)
                user_msg = query_params.get("text", [""])[0]
                
                # Get serial number from r1-serial header
                serial = request.headers.get("r1-serial")
                if not serial:
                    # Fallback to serial query param if header missing
                    # some clients might send it as param
                    serial = query_params.get("serial", [""])[0]
                    if not serial:
                        return Response.json({"error": "Missing r1-serial header or serial query param"}, status=400)
                
                # Fetch config from KV
                # In wrangler.jsonc, KV namespace binding is R1
                kv_key = f"device:{serial}"
                config_str = await self.env.R1.get(kv_key)
                if not config_str:
                    return Response.json({"error": f"Device {serial} not found in KV"}, status=404)
                
                device_config = json.loads(config_str)
                
                return await self.process_chat(user_msg, device_config)
            
            # Default fall-through
            return Response.json({"error": "Endpoint not found"}, status=404)

        except Exception as e:
            print(f"Error: {e}")
            return Response.json(
                {"error": str(e), "type": type(e).__name__},
                status=500,
            )

    # MARK: - Chat Processing Handler

    async def process_chat(self, message, device_config):
        """Process chat request with specific device config."""
        ai_config = device_config.get("aiConfig", {})
        
        model = ai_config.get("model")
        endpoint = ai_config.get("endpoint")
        cdn = ai_config.get("cdn")
        api_key = ai_config.get("key")
        system_prompt = ai_config.get("systemPrompt")
        extra_body_str = ai_config.get("extraBody", "{}")
        
        try:
            extra_body = json.loads(extra_body_str)
        except:
            extra_body = {}

        ai_server = endpoint
        if cdn:
            ai_server = cdn
            extra_body['real'] = endpoint

        # Initialize LLM with device's AI configuration
        llm = ChatOpenAI(
            model=model,
            base_url=ai_server,
            api_key=api_key,
            temperature=0.0,
            streaming=False,
            extra_body=extra_body
        )
        
        # Initialize tools with device context
        r1_tools = R1Tools(device_config)
        all_tools = r1_tools.get_all_tools()
        
        llm_with_tools = llm.bind_tools(all_tools)

        # Prepare messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]

        response = llm_with_tools.invoke(messages)

        if response.tool_calls:
            # Map tools by their name
            TOOL_MAP = {tool.name: tool for tool in all_tools}
            
            tc = response.tool_calls[0]
            tool = TOOL_MAP.get(tc["name"])
            
            if tool:
                result = tool.invoke(tc["args"])
                # If result is a dict, it's the structured box client response
                if isinstance(result, dict):
                    return Response.json(result)
                else:
                    return Response.json({
                        "general": {"text": str(result), "type": "T"},
                        "code": "SETTING_EXEC"
                    })
            else:
                return Response.json({
                    "general": {"text": f"Warning: tool '{tc['name']}' unknown", "type": "T"},
                    "error": response.content
                })

        # Regular assistant response
        return Response.json({
            "general": {"text": response.content, "type": "T"},
            "code": "CHAT_RESP"
        })

"""LangChain + Cloudflare Python Worker Example.

Features demonstrated:
- Custom endpoint routing
- KV retrieval for device-specific config
- Dynamic LLM and tool configuration
- Tool calling with device context
- Return structured responses for box-client
"""

import json
import time
import base64
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
            if path == "/r1/ai/chat/completions":
                # Get user input from POST body
                try:
                    body = await request.json()
                    messages = body.get("messages", [])
                except:
                    messages = []

                # Get serial number from r1-serial header
                serial = request.headers.get("r1-serial")
                if not serial:
                    # Fallback to serial query param if header missing
                    query_params = parse_qs(url.query)
                    serial = query_params.get("serial", [""])[0]
                    if not serial:
                        return Response.json({"error": "Missing r1-serial header or serial query param"}, status=400)
                
                # Fetch config from KV (try serial first, then default)
                device_config = None
                now_ms = int(time.time() * 1000)
                
                # 1. Try specific serial config
                kv_key = f"device:{serial}"
                config_str = await self.env.R1.get(kv_key)
                if config_str:
                    try:
                        cfg = json.loads(config_str)
                        expire_at = cfg.get("expireAt")
                        if not expire_at or now_ms <= expire_at:
                            device_config = cfg
                        else:
                            print(f"Config for {serial} expired at {expire_at}, fallback to default")
                    except Exception as e:
                        print(f"Error parsing config for {serial}: {e}")

                # 2. Fallback to default if needed
                if not device_config:
                    config_str = await self.env.R1.get("device:DEFAULT")
                    if config_str:
                        try:
                            device_config = json.loads(config_str)
                            # Optional: Check if default itself is expired
                            expire_at = device_config.get("expireAt")
                            if expire_at and now_ms > expire_at:
                                return Response.json({"error": "Default configuration also expired", "code": 403}, status=403)
                        except Exception as e:
                            print(f"Error parsing default config: {e}")
                
                if not device_config:
                    return Response.json({"error": f"Configuration not found for device {serial} or default"}, status=404)
                
                # Extract and decode AI config from header as fallback
                ai_header_config = {}
                x_r1_ai = request.headers.get("x-r1-ai")
                if x_r1_ai:
                    try:
                        decoded = base64.b64decode(x_r1_ai).decode('utf-8')
                        ai_header_config = json.loads(decoded)
                    except Exception as e:
                        print(f"Error decoding x-r1-ai header: {e}")

                return await self.process_chat(messages, device_config, ai_header_config, request)
            
            # Default fall-through
            return Response.json({"error": "Endpoint not found"}, status=404)

        except Exception as e:
            print(f"Error: {e}")
            return Response.json(
                {"error": str(e), "type": type(e).__name__},
                status=500,
            )

    # MARK: - Chat Processing Handler

    async def process_chat(self, messages, device_config, ai_header_config=None, request=None):
        """Process chat request with specific device config."""
        ai_config = device_config.get("aiConfig")
        if not ai_config or not ai_config.get("key"):
            ai_config = ai_header_config or {}
        
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
        
        # Collect request headers for tools
        request_headers = {}
        if request is not None:
            try:
                for key in request.headers.keys():
                    request_headers[key.lower()] = request.headers.get(key)
            except Exception as e:
                print(f"Error reading request headers: {e}")
        
        # Initialize tools with device context and request headers
        r1_tools = R1Tools(device_config, request_headers)
        all_tools = r1_tools.get_all_tools()
        
        llm_with_tools = llm.bind_tools(all_tools)

        # Build UTC+8 time prefix for system prompt
        try:
            now_utc8 = time.gmtime(time.time() + 8 * 3600)
            time_str = time.strftime("%Y年%m月%d日 %H:%M", now_utc8)
            weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            weekday_str = weekdays[now_utc8.tm_wday]
            time_context = f"当前时间：{time_str}（{weekday_str}）（UTC+8）"
        except Exception as e:
            print(f"Error building time context: {e}")
            time_context = ""

        # Prepare messages
        if system_prompt or time_context:
            has_system = any(m.get("role") == "system" for m in messages)
            if not has_system:
                full_system = f"{time_context}\n{system_prompt}" if (time_context and system_prompt) else (time_context or system_prompt or "")
                messages.insert(0, {"role": "system", "content": full_system})

        response = await llm_with_tools.ainvoke(messages)

        if response.tool_calls:
            # Map tools by their name
            TOOL_MAP = {tool.name: tool for tool in all_tools}
            
            tc = response.tool_calls[0]
            tool = TOOL_MAP.get(tc["name"])
            
            if tool:
                result = await tool.invoke(tc["args"])
                # If result is a dict, it's the structured box client response
                if isinstance(result, dict):
                    # Extract r1 headers if present
                    r1_headers = result.pop("_r1_headers", None)
                    return Response.json(result, headers=r1_headers)
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

        # Regular assistant response (TTS fall-through)
        return Response.json({
            "code": "ANSWER",
            "matchType": "NOT_UNDERSTAND",
            "confidence": 0.8,
            "history": "cn.yunzhisheng.chat",
            "source": "nlu",
            "asr_recongize": "OK",
            "rc": 0,
            "general": {
                "style": "CQA_common_customized",
                "text": response.content,
                "type": "T",
                "resourceId": "904757"
            },
            "returnCode": 0,
            "audioUrl": "http://asrv3.hivoice.cn/trafficRouter/r/TRdECS",
            "retTag": "nlu",
            "service": "cn.yunzhisheng.chat",
            "nluProcessTime": "717",
            "text": "OK",
            "responseId": "9a83414b09024d9d85df88aa07cad8c9"
        })

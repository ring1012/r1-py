from tool_decorator import tool
from typing import Optional, Any
import json
import base64
from workers import fetch
import uuid


class R1Tools:
    def __init__(self, device_config: dict, request_headers: dict = None, providers_config: dict = None):
        self.device_config = device_config
        self.request_headers = request_headers or {}
        self.providers_config = providers_config or {}
        self.intent = {
            "intent": {
                "operations": [
                    {"operator": "ACT_PLAY"}
                ]
            }
        }

    def _base_response(self, text: str, service: str = "cn.yunzhisheng.music"):
        return {
            "semantic": self.intent,
            "code": "SETTING_EXEC",
            "matchType": "FUZZY",
            "general": {
                "text": text,
                "type": "T"
            },
            "service": service
        }

    def _resolve_endpoint(self, header_key: str, service_type: str, device_config_key: str) -> str:
        """Resolve the best endpoint for a service.
        1. Decode the device header to get the preferred provider name.
        2. Iterate providers_config[service_type] list to find a matching entry.
        3. Fallback to the device's own config endpoint if no match found.
        """
        preferred_provider = ""
        header_val = self.request_headers.get(header_key, "")
        if header_val:
            try:
                decoded = base64.b64decode(header_val).decode("utf-8")
                prefs = json.loads(decoded)
                preferred_provider = prefs.get("provider", "")
            except Exception as e:
                print(f"Error decoding {header_key} header: {e}")

        # Iterate providers list to find matching provider
        if preferred_provider and preferred_provider != "default":
            provider_list = self.providers_config.get(service_type, [])
            if isinstance(provider_list, list):
                for entry in provider_list:
                    if isinstance(entry, dict) and entry.get("provider") == preferred_provider:
                        endpoint = entry.get("endpoint", "").rstrip("/")
                        if endpoint:
                            print(f"[{service_type}] matched provider '{preferred_provider}' -> {endpoint}")
                            return endpoint
                print(f"[{service_type}] provider '{preferred_provider}' not found in providers list, using device default")

        # Fallback to device config endpoint
        return self.device_config.get(device_config_key, {}).get("endpoint", "")

    async def _fetch_media(self, config_key: str, search_key: str, info_key: str, endpoint_override: str = ""):
        config = self.device_config.get(config_key, {})
        endpoint = endpoint_override or config.get("endpoint", "")
        data = {"count": 0, info_key: []}
        r1_headers = {}
        if endpoint:
            try:
                search_url = f"{endpoint}/search?keyword={search_key}"
                print(f"{config_key} search: {search_url}")
                resp = await fetch(search_url)
                if resp.ok:
                    data = await resp.json()
                    for key in resp.headers.keys():
                        if key.lower().startswith("x-r1"):
                            r1_headers[key] = resp.headers.get(key)
                r1_headers["r1-sname"] = "cn.yunzhisheng.music"
            except Exception as e:
                print(f"{config_key} search error: {e}")
        return data, r1_headers

    def _build_playback_response(self, data: dict, display_text: str, service: str, r1_headers: dict = None):
        ret = {
            "semantic": self.intent,
            "code": "SETTING_EXEC",
            "matchType": "FUZZY",
            "originIntent": {"nluSlotInfos": []},
            "data": {"result": data},
            "confidence": 0.6313702287003818,
            "modelIntentClsScore": {},
            "history": "cn.yunzhisheng.setting.mp",
            "source": "nlu",
            "uniCarRet": {
                "result": {},
                "returnCode": 609,
                "message": "http post reuqest error"
            },
            "asr_recongize": f"播放{display_text}。",
            "rc": 0,
            "general": {
                "text": f"好的，已为您播放{display_text}",
                "type": "T"
            },
            "returnCode": 0,
            "retTag": "nlu",
            "service": service,
            "nluProcessTime": "255",
            "text": f"播放{display_text}",
            "responseId": str(uuid.uuid4()).replace("-", "")
        }
        if r1_headers:
            ret["_r1_headers"] = r1_headers
        return ret

    @tool
    async def chat(self, answer: str) -> dict:
        """用于回答用户的普通问题、闲聊、知识问答等。
        当用户的问题不属于音乐、新闻、天气、智能家居等特定功能时，使用此工具回复。
        samples: 什么是人工智能、地球为什么是圆的、1+1等于几、你好、今天心情不好、给我讲个笑话
        
        Args:
            answer: 回复用户的内容
        """
        return {
            "code": "ANSWER",
            "matchType": "NOT_UNDERSTAND",
            "confidence": 0.8,
            "history": "cn.yunzhisheng.chat",
            "source": "nlu",
            "asr_recongize": "OK",
            "rc": 0,
            "general": {
                "style": "CQA_common_customized",
                "text": answer,
                "type": "T",
                "resourceId": "904757"
            },
            "returnCode": 0,
            "audioUrl": "http://asrv3.hivoice.cn/trafficRouter/r/TRdECS",
            "retTag": "nlu",
            "service": "cn.yunzhisheng.chat",
            "nluProcessTime": "717",
            "text": "OK",
            "responseId": "9a83414b09024d9d85df88aa07cad8c9",
            "_r1_headers": {"r1-sname": "cn.yunzhisheng.chat"}
        }

    @tool
    async def playMusic(self, author: Optional[str] = "", song_name: Optional[str] = "", keyword: Optional[str] = "", playlist_name: Optional[str] = "") -> dict:
        """用于播放音乐、歌曲。当用户想听歌、听音乐时调用此工具。
        samples: 我想听刀郎的歌、播放夜曲、播放周杰伦的歌、听音乐、来首歌、播放我的收藏、播放歌单、放首歌、听首歌、来点音乐
        
        Args:
            author: 歌曲作者，可以为空字符串
            song_name: 歌曲名称，可以为空字符串
            keyword: 歌曲搜索关键词，可以为空字符串
            playlist_name: 歌单名称，比如"我的收藏"
        """
        if playlist_name:
            # 播放歌单逻辑
            serial = self.request_headers.get("r1-serial", "")
            headers = {"x-r1-serial": serial}
            playlist_url = f"https://air1.pp.ua/api/music/song-list?keyword={playlist_name}"
            
            data = {"count": 0, "musicinfo": []}
            try:
                print(f"[playlist] fetching playlist: {playlist_name}")
                resp = await fetch(playlist_url, headers=headers)
                if resp.ok:
                    data = await resp.json()
            except Exception as e:
                print(f"[playlist] error: {e}")
            
            r1_headers = {"r1-sname": "cn.yunzhisheng.music"}
            ret = self._build_playback_response(data, playlist_name, "cn.yunzhisheng.music", r1_headers)
            ret["audioUrl"] = "http://asrv3.hivoice.cn/trafficRouter/r/yxOMl6"
            return ret

        # 普通音乐搜索逻辑
        search_key = keyword or f"{author} {song_name}".strip()
        music_endpoint = self._resolve_endpoint("x-r1-music", "music", "musicConfig")
        data, r1_headers = await self._fetch_media("musicConfig", search_key, "musicinfo", music_endpoint)
        
        music_text = f"{author} {song_name}".strip() or keyword or "音乐"
        ret = self._build_playback_response(data, music_text, "cn.yunzhisheng.music", r1_headers)
        ret["audioUrl"] = "http://asrv3.hivoice.cn/trafficRouter/r/yxOMl6"
        return ret

    @tool
    async def homeassistant(self, target_name: str, control_params: Optional[str] = "", success_prompt: str = "", fail_prompt: str = "") -> dict:
        """智能家居控制与状态查询。

        【核心规则】判断查询还是控制：
        - 用户只提到设备名称 + 属性名称 = 查询该属性的当前值
        - 用户明确要求改变设备状态 = 控制操作

        【判断示例】以下都是【查询】，control_params 必须为空：
        - "主卧空调" → 查询主卧空调状态
        - "主卧空调温度" → 查询当前温度设置（不是调温度！）
        - "主卧空调模式" → 查询当前模式（不是改模式！）
        - "客厅灯亮度" → 查询当前亮度（不是调亮度！）
        - "客厅灯开关状态" → 查询是否开着
        - "热水器温度" → 查询当前温度
        - "卧室空调状态" → 查询状态
        - "空调制冷还是制热" → 查询当前模式
        - "空调几度" → 查询当前温度

        【判断示例】以下才是【控制】，需要填写 control_params（分绝对值/相对值两种）：
        绝对值（用户说"调到XX"）：直接给最终值，无需查询
        - "把主卧空调调到26度" → {"service":"set_temperature","service_data":{"temperature":26}}
        - "亮度调到50" → {"service":"turn_on","service_data":{"brightness":128}}
        - "热水器温度调到40度" → {"service":"set_temperature","service_data":{"temperature":40}}
        相对值（用户说"加/减XX"）：用 delta，无需知道当前值，dummy 会查当前值换算
        - "空调温度调高一度/调低一度" → {"service":"set_temperature","service_data":{"delta":1}} / {"service":"set_temperature","service_data":{"delta":-1}}
        - "温度加2度" → {"service":"set_temperature","service_data":{"delta":2}}
        - "热水器温度调高一度" → {"service":"set_temperature","service_data":{"delta":1}}
        - "亮度调高/调低" → {"service":"turn_on","service_data":{"delta":1}} / {"service":"turn_on","service_data":{"delta":-1}}
        - "亮度加30" → {"service":"turn_on","service_data":{"delta":30}}
        其他： "打开客厅灯" → {"service":"turn_on"} / "关灯" → {"service":"turn_off"} / "空调调成制冷" → {"service":"set_hvac_mode","service_data":{"hvac_mode":"cool"}} / "空调开到28度" → {"service":"set_temperature","service_data":{"temperature":28}}
        - "空调风速调到自动/静音/低风/中风/高风" → {"service":"set_fan_mode","service_data":{"fan_mode":"auto"}} / "silent" / "low" / "medium" / "high"
        - "空调扫风打开/关闭" → {"service":"set_swing_mode","service_data":{"swing_mode":"on"}} / {"service":"set_swing_mode","service_data":{"swing_mode":"off"}}

        【简单判断法】
        如果用户的句子中包含"调到"、"打开"、"关闭"、"开"、"关"、"设置为"等动作词 = 控制
        如果用户的句子只是提到设备名称或属性名称 = 查询

        control_params 格式根据设备 domain 不同（注意：所有 service_data 字段必须放在 service_data 对象内，不要放在顶层）：
        light: service 为 turn_on/turn_off/toggle，service_data 可选字段 brightness(0-255)、color_temp(整数)、rgb_color([r,g,b])；支持相对调节 {"service":"turn_on","service_data":{"delta":1}} 默认步进+25，用户可指定 {"delta":30}
        switch: service 为 turn_on/turn_off/toggle，无可选字段；
        climate: service 为 set_hvac_mode，字段 hvac_mode("heat"/"cool"/"auto"/"off")；
        或 service 为 set_temperature，字段 temperature(浮点数)；支持相对 {"service":"set_temperature","service_data":{"delta":1}} 默认±1度，用户可指定 {"delta":2}
        或 service 为 set_fan_mode，字段 fan_mode(字符串)；支持相对调档 delta:1 表示档位+1
        或 service 为 set_swing_mode，字段 swing_mode(字符串)；
        fan: service 为 turn_on/turn_off/set_speed/oscillate，service_data 可选字段 speed("off"/"low"/"medium"/"high"/"auto")、oscillation(布尔值)；支持 delta:1 档位步进
        cover: service 为 open_cover/close_cover/stop_cover/set_cover_position，service_data 可选字段 position(0-100)；支持 {"delta":10} 默认±10%
        media_player: service 为 media_play/media_pause/media_stop/volume_set/volume_mute，service_data 可选字段 volume_level(0.0-1.0)、is_volume_muted(布尔值)；支持 {"delta":0.1}
        vacuum: service 为 start/stop/pause/return_to_base，无可选字段；
        lock: service 为 lock/unlock，无可选字段；
        humidifier: service 为 turn_on/turn_off/set_humidity/set_mode，service_data 可选字段 humidity(整数)、mode(字符串)；支持 {"delta":1} 默认±5%
        water_heater: service 为 turn_on/turn_off/set_temperature，service_data 可选字段 temperature(浮点数)；支持 {"delta":1}
        
        Args:
            target_name: 用户要操作的实体名称，如"主卧空调"、"客厅灯"、"热水器"，必须从用户原话中提取
            control_params: JSON 对象，包含 service 和 service_data。仅当用户明确要求控制设备时才填写，否则留空字符串。示例：{"service":"turn_on","service_data":{"brightness":128}}
            success_prompt: 操作成功时返回给用户的话术模板
            fail_prompt: 操作失败时返回给用户的话术模板
        """
        result = {
            "target_name": target_name,
            "control_params": control_params or "",
            "success_prompt": success_prompt,
            "fail_prompt": fail_prompt
        }
        return {
            "code": "ANSWER",
            "matchType": "NOT_UNDERSTAND",
            "originIntent": {"nluSlotInfos": []},
            "confidence": 0.088038474,
            "modelIntentClsScore": {},
            "history": "cn.yunzhisheng.chat",
            "source": "krc",
            "uniCarRet": {
                "result": {},
                "returnCode": 609,
                "message": "http post reuqest error"
            },
            "asr_recongize": "hello world",
            "rc": 0,
            "general": {"text": json.dumps(result, ensure_ascii=False), "type": "T"},
            "returnCode": 0,
            "audioUrl": "http://asrv3.hivoice.cn/trafficRouter/r/0bXs9E",
            "retTag": "nlu",
            "service": "cn.yunzhisheng.custom",
            "nluProcessTime": "648",
            "text": "控制完成",
            "responseId": "9a83414b09024d9d85df88aa07cad8c9",
            "_r1_headers": {"r1-sname": "cn.yunzhisheng.custom"}
        }

    @tool
    async def playNews(self, user_input: str) -> dict:
        """用于播放新闻、收听新闻节目。
        当用户想听新闻时调用此工具。
        samples: 播放新闻、听新闻、来点新闻、最新新闻、今天新闻、新闻播报、整点新闻、国内新闻、国际新闻、体育新闻、财经新闻
        
        Args:
            user_input: 用户输入关键词或描述，如"国内新闻"、"体育新闻"
        """
        url = "https://apppc.cnr.cn/cnr45609411d2c5a16/e281277129d478c12c2ed58e84ca906b/f76a0411ae1ff31be9f9e28f0b51348b"
        
        body = {
            "chanId": "64", # 中国之声
            "pageIndex": 1,
            "perPage": 40,
            "lastNewsId": "0",
            "docPubTime": ""
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.cnr.cn/",
            "Origin": "https://www.cnr.cn"
        }
        
        data = {"count": 0, "musicinfo": []}
        try:
            print(f"[news] fetching from cnr...")
            resp = await fetch(url, method="POST", headers=headers, body=json.dumps(body))
            if resp.ok:
                res_js = await resp.json()
                categories = res_js.get("data", {}).get("categories", [])
                if categories:
                    items = categories[0].get("detail", [])
                    music_info = []
                    for idx, item in enumerate(items):
                        link = item.get("other_info9", "")
                        if not link or "m3u8" in link:
                            continue
                        music_info.append({
                            "id": idx,
                            "title": item.get("title", "新闻"),
                            "artist": "中国之声",
                            "url": link
                        })
                    data = {
                        "count": len(music_info),
                        "musicinfo": music_info,
                        "pagesize": str(len(music_info)),
                        "errorCode": 0,
                        "page": "1",
                        "source": 1
                    }
        except Exception as e:
            print(f"[news] error: {e}")
            
        r1_headers = {"r1-sname": "cn.yunzhisheng.music"}
        return self._build_playback_response(data, "新闻", "cn.yunzhisheng.music", r1_headers)

    @tool
    async def playAudio(self, keyword: str) -> dict:
        """用于播放故事、有声读物、广播剧、相声、评书等音频内容。
        samples: 我想看三体、播放三体有声读物、听故事、来个故事、播放相声、听评书、播放广播剧、有声小说
        
        Args:
            keyword: 关键词，如书名、故事名、相声名等
        """
        story_endpoint = self._resolve_endpoint("x-r1-story", "story", "audioConfig")
        data, r1_headers = await self._fetch_media("audioConfig", keyword, "audioinfo", story_endpoint)
        return self._build_playback_response(data, keyword, "cn.yunzhisheng.music", r1_headers)

    @tool
    async def playRadio(self, radio_name: str) -> dict:
        """用于播放广播电台节目。
        samples: 我想听上海交通广播、播放收音机、听广播、中央人民广播电台、中国之声、调频FM
        
        Args:
            radio_name: 广播电台名称
        """
        data, _ = await self._fetch_media("radioConfig", radio_name, "radioinfo")
        link = ""
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], dict):
                link = data["data"].get("url", "")
            else:
                link = data.get("url", "")

        response_id = str(uuid.uuid4()).replace("-", "")
        return {
            "code": "ANSWER",
            "matchType": "NOT_UNDERSTAND",
            "originIntent": {"nluSlotInfos": []},
            "confidence": 0.088038474,
            "modelIntentClsScore": {},
            "history": "cn.yunzhisheng.chat",
            "source": "krc",
            "uniCarRet": {
                "result": {},
                "returnCode": 609,
                "message": "http post reuqest error"
            },
            "asr_recongize": f"{radio_name}。",
            "rc": 0,
            "general": {
                "style": "translation",
                "audio": link,
                "mood": "中性",
                "text": f"好的，已为您播放 {radio_name}"
            },
            "returnCode": 0,
            "audioUrl": "http://asrv3.hivoice.cn/trafficRouter/r/0bXs9E",
            "retTag": "nlu",
            "service": "cn.yunzhisheng.chat",
            "nluProcessTime": "648",
            "text": radio_name,
            "responseId": response_id
        }

    def _get_weather_config(self):
        """从 device_config 或 x-r1-weather header 中获取天气配置 {endpoint, apiKey}"""
        # 1. 优先从 KV device_config 中读取
        cfg = self.device_config.get("weatherConfig", {})
        if cfg.get("endpoint") and cfg.get("apiKey"):
            return cfg
        # 2. fallback: 从 x-r1-weather header 解码
        weather_header = self.request_headers.get("x-r1-weather", "")
        if weather_header:
            try:
                decoded = base64.b64decode(weather_header).decode("utf-8")
                return json.loads(decoded)
            except Exception as e:
                print(f"Error decoding x-r1-weather header: {e}")
        return {}

    def _get_location(self):
        """从请求头获取经纬度，返回 (latitude, longitude) 字符串元组，可能为 None"""
        lat = self.request_headers.get("x-r1-latitude") or self.request_headers.get("cf-latitude")
        lon = self.request_headers.get("x-r1-longitude") or self.request_headers.get("cf-longitude")
        return lat, lon

    @tool
    async def queryWeather(self, location_name: Optional[str] = "", offset_day: Optional[int] = 0) -> dict:
        """用于查询天气信息。当用户想知道天气情况时调用此工具。
        samples: 今天什么天气、明天天气怎么样、后天会下雨吗、上海天气、北京明天天气、今天几度、会下雨吗、需要带伞吗、这周天气
        
        Args:
            location_name: 位置名，如"上海"、"北京"，为空则使用当前位置
            offset_day: 偏移天数，0表示今天，1表示明天，2表示后天，以此类推
        """
        weather_cfg = self._get_weather_config()
        endpoint = weather_cfg.get("endpoint", "").rstrip("/")
        api_key = weather_cfg.get("apiKey", "")

        if not endpoint or not api_key:
            raise Exception("天气服务未配置，请在服务配置中填写 QWeather 的 Endpoint 和 API Key。")

        headers = {"X-QW-Api-Key": api_key, "Accept-Encoding": "gzip"}

        try:
            # ── 1. 解析经纬度 ──────────────────────────────────────────────
            lat, lon = self._get_location()

            # 优先使用 location_name，如果没有则使用当前坐标反查地名
            geo_query = location_name if location_name else (f"{lon},{lat}" if (lat and lon) else None)
            location_label = location_name or "当地"

            if geo_query:
                geo_url = f"{endpoint}/geo/v2/city/lookup?location={geo_query}"
                print(f"[weather] geo lookup: {geo_url}")
                geo_resp = await fetch(geo_url, headers=headers)
                if geo_resp.ok:
                    geo_data = await geo_resp.json()
                    locations = geo_data.get("location", [])
                    if locations:
                        lat = str(locations[0].get("lat", lat))
                        lon = str(locations[0].get("lon", lon))
                        location_label = locations[0].get("name", location_label)

            if not lat or not lon:
                return {
                    "general": {"text": "无法获取位置信息，请确保设备已开启定位或指定城市名称。", "type": "T"},
                    "code": "SETTING_EXEC",
                    "service": "cn.yunzhisheng.weather"
                }

            location_param = f"{lon},{lat}"  # QWeather 格式: 经度,纬度

            # ── 2. 查询7天天气预报 ─────────────────────────────────────────
            day_url = f"{endpoint}/v7/weather/7d?location={location_param}"
            print(f"[weather] 7d: {day_url}")
            day_resp = await fetch(day_url, headers=headers)
            if not day_resp.ok:
                raise Exception(f"7d weather API error: {day_resp.status}")
            day_data = await day_resp.json()
            daily_list = day_data.get("daily", [])

            if offset_day >= len(daily_list):
                offset_day = len(daily_list) - 1
            if not daily_list:
                raise Exception("No daily weather data returned")

            day = daily_list[offset_day]
            if offset_day == 0:
                day_label = "今天"
            elif offset_day == 1:
                day_label = "明天"
            elif offset_day == 2:
                day_label = "后天"
            else:
                day_label = f"{offset_day}天后"

            text_day   = day.get("textDay", "")
            temp_max   = day.get("tempMax", "")
            temp_min   = day.get("tempMin", "")
            wind_dir   = day.get("windDirDay", "")
            wind_scale = day.get("windScaleDay", "")

            parts = [
                f"{location_label}{day_label}的天气：{text_day}，",
                f"气温{temp_min}°C到{temp_max}°C，",
                f"{wind_dir}{wind_scale}级风。"
            ]

            # ── 3. 今天额外查询 ────────────────────────────────────────────
            if offset_day == 0:
                # 3a. 逐小时预报 - 查找下一场雨
                try:
                    hour_url = f"{endpoint}/v7/weather/24h?location={location_param}"
                    hour_resp = await fetch(hour_url, headers=headers)
                    if hour_resp.ok:
                        hour_data = await hour_resp.json()
                        hourly_list = hour_data.get("hourly", [])
                        if hourly_list:
                            first_icon = int(hourly_list[0].get("icon", "100") or "100")
                            if first_icon > 200:  # 当前就在下雨/雪
                                first = hourly_list[0]
                                fx_time = first.get("fxTime", "")  # e.g. 2021-02-16T16:00+08:00
                                hour_part = fx_time[11:16] if len(fx_time) >= 16 else ""
                                rain_text = first.get("text", "")
                                parts.append(f"目前{hour_part}开始{rain_text}。")
                            else:
                                # 找第一个 icon > 200 的时段
                                for h in hourly_list[1:]:
                                    icon_val = int(h.get("icon", "100") or "100")
                                    if icon_val > 200:
                                        fx_time = h.get("fxTime", "")
                                        hour_part = fx_time[11:16] if len(fx_time) >= 16 else ""
                                        rain_text = h.get("text", "")
                                        parts.append(f"{hour_part}后开始{rain_text}。")
                                        break
                except Exception as e:
                    print(f"[weather] hourly error: {e}")

                # 3b. 天气预警
                try:
                    alert_url = f"{endpoint}/weatheralert/v1/current/{lat}/{lon}"
                    alert_resp = await fetch(alert_url, headers=headers)
                    if alert_resp.ok:
                        alert_data = await alert_resp.json()
                        alerts = alert_data.get("alerts", [])
                        for a in alerts:
                            desc = a.get("description", "")
                            if desc:
                                parts.append(f"{desc}")
                except Exception as e:
                    print(f"[weather] alert error: {e}")

            # ── 4. 生活指数 ────────────────────────────────────────────────
            try:
                indices_url = f"{endpoint}/v7/indices/1d?type=1,3&location={location_param}"
                indices_resp = await fetch(indices_url, headers=headers)
                if indices_resp.ok:
                    indices_data = await indices_resp.json()
                    indices_daily = indices_data.get("daily", [])
                    if offset_day < len(indices_daily):
                        idx_text = indices_daily[offset_day].get("text", "")
                        if idx_text:
                            parts.append(f"{idx_text}")
                    elif indices_daily:
                        idx_text = indices_daily[0].get("text", "")
                        if idx_text:
                            parts.append(f"{idx_text}")
            except Exception as e:
                print(f"[weather] indices error: {e}")

            msg = "".join(parts)

        except Exception as e:
            print(f"[weather] error: {e}")
            msg = f"天气查询失败：{str(e)}"
            raise e

        return  {
            "code": "ANSWER",
            "matchType": "NOT_UNDERSTAND",
            "confidence": 0.8,
            "history": "cn.yunzhisheng.chat",
            "source": "nlu",
            "asr_recongize": "OK",
            "rc": 0,
            "general": {
                "style": "CQA_common_customized",
                "text": msg,
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
        }

    def get_all_tools(self):
        return [
            self.chat,
            self.playMusic,
            self.homeassistant,
            self.playNews,
            self.playAudio,
            self.playRadio,
            self.queryWeather
        ]

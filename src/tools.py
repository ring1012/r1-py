from tool_decorator import tool
from typing import Optional, Any
import json
import base64
from workers import fetch
import uuid


class R1Tools:
    def __init__(self, device_config: dict, request_headers: dict = None):
        self.device_config = device_config
        self.request_headers = request_headers or {}
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

    async def _fetch_media(self, config_key: str, search_key: str, info_key: str):
        config = self.device_config.get(config_key, {})
        endpoint = config.get("endpoint", "")
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
    async def playMusic(self, author: Optional[str] = "", song_name: Optional[str] = "", keyword: Optional[str] = "") -> dict:
        """用于处理播放音乐请求，比如流行歌曲，儿歌等等.
        samples: 我想听刀郎的歌，播放夜曲
        
        Args:
            author: 歌曲作者，可以为空字符串
            song_name: 歌曲名称，可以为空字符串
            keyword: 歌曲搜索关键词，可以为空字符串
        """
        search_key = keyword or f"{author} {song_name}".strip()
        data, r1_headers = await self._fetch_media("musicConfig", search_key, "musicinfo")
        
        music_text = f"{author} {song_name}".strip() or keyword or "音乐"
        ret = self._build_playback_response(data, music_text, "cn.yunzhisheng.music", r1_headers)
        ret["audioUrl"] = "http://asrv3.hivoice.cn/trafficRouter/r/yxOMl6"
        return ret

    @tool
    def homeassistant(self, target: str, act_value: str, parameter: Optional[str] = "") -> dict:
        """智能家居控制，比如打开灯、热得快，空调，调节温度，查询湿度，等等
        sample: 把客厅空调温度调整为23度 -> target=客厅空调 parameter=temperature actValue=23
        
        Args:
            target: 控制对象：主卧空调，热得快。输出中文
            parameter: 属性：温度（temperature），风速。输出英文
            act_value: 动作或值：打开(on), 关闭(off)， 23，不需要单位。
        """
        # hass_config = self.device_config.get("hassConfig", {})
        msg = f"已经为您执行：{target} {parameter or ''} 设置为 {act_value}"
        return {
            "general": {"text": msg, "type": "T"},
            "code": "SETTING_EXEC",
            "service": "cn.yunzhisheng.setting"
        }

    @tool
    def playNews(self, user_input: str) -> dict:
        """用于播放新闻。
        samples: 播放新闻
        
        Args:
            user_input: 用户输入关键词或描述
        """
        resp = self._base_response("好的，已为您播放新闻")
        resp["data"] = {"type": "news", "query": user_input}
        return resp

    @tool
    async def playAudio(self, keyword: str) -> dict:
        """用于播放故事、视频、有声读物等。
        samples: 我想看三体，播放三体有声读物
        
        Args:
            keyword: 关键词
        """
        data, r1_headers = await self._fetch_media("audioConfig", keyword, "audioinfo")
        return self._build_playback_response(data, keyword, "cn.yunzhisheng.music", r1_headers)

    @tool
    async def playRadio(self, radio_name: str) -> dict:
        """用于播放广播
        samples: 我想听上海交通广播
        
        Args:
            radio_name: 广播名称
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
        """用于查询天气，位置名默认为空字符串
        samples: 后天什么天气 -> locationName="" offsetDay=2
        
        Args:
            location_name: 位置名
            offset_day: offsetDay，0表示今天，1表示明天，以此类推
        """
        weather_cfg = self._get_weather_config()
        endpoint = weather_cfg.get("endpoint", "").rstrip("/")
        api_key = weather_cfg.get("apiKey", "")

        if not endpoint or not api_key:
            return {
                "general": {"text": "天气服务未配置，请在服务配置中填写 QWeather 的 Endpoint 和 API Key。", "type": "T"},
                "code": "SETTING_EXEC",
                "service": "cn.yunzhisheng.weather"
            }

        headers = {"X-QW-Api-Key": api_key, "Accept-Encoding": "gzip"}

        try:
            # ── 1. 解析经纬度 ──────────────────────────────────────────────
            lat, lon = self._get_location()

            if location_name:
                # 用地名换取经纬度
                geo_url = f"{endpoint}/geo/v2/city/lookup?location={location_name}"
                print(f"[weather] geo lookup: {geo_url}")
                geo_resp = await fetch(geo_url, headers=headers)
                if geo_resp.ok:
                    geo_data = await geo_resp.json()
                    locations = geo_data.get("location", [])
                    if locations:
                        lat = str(locations[0].get("lat", lat))
                        lon = str(locations[0].get("lon", lon))

            if not lat or not lon:
                return {
                    "general": {"text": "无法获取位置信息，请确保设备已开启定位或指定城市名称。", "type": "T"},
                    "code": "SETTING_EXEC",
                    "service": "cn.yunzhisheng.weather"
                }

            location_param = f"{lon},{lat}"  # QWeather 格式: 经度,纬度
            location_label = location_name or "当地"

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
                f"最高气温 {temp_max}°C，最低气温 {temp_min}°C，",
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
                                parts.append(f"⚠️预警：{desc}")
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
                            parts.append(f"建议：{idx_text}")
                    elif indices_daily:
                        idx_text = indices_daily[0].get("text", "")
                        if idx_text:
                            parts.append(f"生活提示：{idx_text}")
            except Exception as e:
                print(f"[weather] indices error: {e}")

            msg = "".join(parts)

        except Exception as e:
            print(f"[weather] error: {e}")
            msg = f"天气查询失败：{str(e)}"

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
            self.playMusic,
            self.homeassistant,
            self.playNews,
            self.playAudio,
            self.playRadio,
            self.queryWeather
        ]

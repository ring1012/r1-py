from tool_decorator import tool
from typing import Optional, Any
import json
from js import fetch
import uuid


class R1Tools:
    def __init__(self, device_config: dict):
        self.device_config = device_config
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
                    res_js = await resp.json()
                    data = res_js.to_py()
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
        search_key = f"{author} {song_name} {keyword}".strip()
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

    @tool
    def queryWeather(self, location_name: Optional[str] = "", offset_day: Optional[int] = 0) -> dict:
        """用于查询天气，位置名默认为空字符串
        samples: 后天什么天气 -> locationName="" offsetDay=2
        
        Args:
            location_name: 位置名
            offset_day: offsetDay，0表示今天，1表示明天，以此类推
        """
        # weather_config = self.device_config.get("weatherConfig", {})
        msg = f"正在查询 {location_name or '本地'} {offset_day} 天后的天气，目前晴到多云。" # 模拟
        return {
            "general": {"text": msg, "type": "T"},
            "code": "SETTING_EXEC",
            "service": "cn.yunzhisheng.weather"
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

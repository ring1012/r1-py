from tool_decorator import tool
from typing import Optional, Any
import json


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

    @tool
    def play_music(self, author: Optional[str] = "", song_name: Optional[str] = "", keyword: Optional[str] = "") -> dict:
        """用于处理播放音乐请求，比如流行歌曲，儿歌等等.
        samples: 我想听刀郎的歌，播放夜曲
        
        Args:
            author: 歌曲作者，可以为空字符串
            song_name: 歌曲名称，可以为空字符串
            keyword: 歌曲搜索关键词，可以为空字符串
        """
        music_config = self.device_config.get("musicConfig", {})
        # endpoint = music_config.get("endpoint", "")
        
        resp = self._base_response(f"好的，已为您播放{author}的{song_name}")
        # 这里模拟返回音乐数据，实际应该调用后端服务
        resp["data"] = {
            "author": author,
            "song": song_name,
            "keyword": keyword,
            "url": "https://example.com/stream.mp3" # 模拟
        }
        return resp

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
    def play_news(self, user_input: str) -> dict:
        """用于播放新闻。
        samples: 播放新闻
        
        Args:
            user_input: 用户输入关键词或描述
        """
        resp = self._base_response("好的，已为您播放新闻")
        resp["data"] = {"type": "news", "query": user_input}
        return resp

    @tool
    def play_audio(self, keyword: str, look: Optional[bool] = False) -> dict:
        """用于播放故事、视频、有声读物等。
        samples: 我想看三体，播放三体有声读物
        
        Args:
            keyword: 关键词
            look: 动作，是否是看视频？
        """
        media_type = "视频" if look else "音频"
        resp = self._base_response(f"好的，已为您播放{media_type}")
        resp["data"] = {"type": "audio", "keyword": keyword, "look": look}
        return resp

    @tool
    def play_radio(self, radio_name: str, province: Optional[str] = "") -> dict:
        """用于播放广播
        samples: 我想听上海交通广播
        
        Args:
            radio_name: 广播名称
            province: 省份
        """
        resp = self._base_response(f"好的，已为您播放广播 {radio_name}")
        resp["data"] = {"type": "radio", "name": radio_name, "province": province}
        return resp

    @tool
    def query_weather(self, location_name: Optional[str] = "", offset_day: Optional[int] = 0) -> dict:
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
            self.play_music,
            self.homeassistant,
            self.play_news,
            self.play_audio,
            self.play_radio,
            self.query_weather
        ]

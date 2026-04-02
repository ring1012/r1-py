from langchain_core.tools import tool
from typing import Optional


@tool
def play_music(author: Optional[str] = "", song_name: Optional[str] = "", keyword: Optional[str] = "") -> str:
    """用于处理播放音乐请求，比如流行歌曲，儿歌等等.
    samples: 我想听刀郎的歌，播放夜曲
    
    Args:
        author: 歌曲作者，可以为空字符串
        song_name: 歌曲名称，可以为空字符串
        keyword: 歌曲搜索关键词，可以为空字符串
    """
    return f"正在为您搜索并播放: {author} {song_name} {keyword}"


@tool
def homeassistant(target: str, act_value: str, parameter: Optional[str] = "") -> str:
    """智能家居控制，比如打开灯、热得快，空调，调节温度，查询湿度，等等
    sample: 把客厅空调温度调整为23度 -> target=客厅空调 parameter=temperature actValue=23
    
    Args:
        target: 控制对象：主卧空调，热得快。输出中文
        parameter: 属性：温度（temperature），风速。输出英文
        act_value: 动作或值：打开(on), 关闭(off)， 23，不需要单位。
    """
    return f"已向智能家居发送指令: {target} {parameter} {act_value}"


@tool
def play_news(user_input: str) -> str:
    """用于播放新闻。
    samples: 播放新闻
    
    Args:
        user_input: 用户输入关键词或描述
    """
    return f"正在为您播放新闻: {user_input}"


@tool
def play_audio(keyword: str, look: Optional[bool] = False) -> str:
    """用于播放故事、视频、有声读物等。
    samples: 我想看三体，播放三体有声读物
    
    Args:
        keyword: 关键词
        look: 动作，是否是看视频？
    """
    media_type = "视频" if look else "音频"
    return f"正在为您播放{media_type}: {keyword}"


@tool
def play_radio(radio_name: str, province: Optional[str] = "") -> str:
    """用于播放广播
    samples: 我想听上海交通广播
    
    Args:
        radio_name: 广播名称
        province: 省份
    """
    return f"正在为您播放广播: {province} {radio_name}"


@tool
def query_weather(location_name: Optional[str] = "", offset_day: Optional[int] = 0) -> str:
    """用于查询天气，位置名默认为空字符串
    samples: 后天什么天气 -> locationName="" offsetDay=2
    
    Args:
        location_name: 位置名
        offset_day: offsetDay，0表示今天，1表示明天，以此类推
    """
    return f"正在查询 {location_name} {offset_day} 天后的天气"


ALL_TOOLS = [
    play_music,
    homeassistant,
    play_news,
    play_audio,
    play_radio,
    query_weather
]

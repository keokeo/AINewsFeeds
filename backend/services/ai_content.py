"""
AI 内容生成服务
负责调用大语言模型对新闻进行总结和排版
"""
import os
import logging
from openai import OpenAI
from typing import List, Dict

from backend.core.config import get, get_int, get_float

logger = logging.getLogger(__name__)


class AiContentService:
    """AI 内容生成服务"""

    def __init__(self, cfg: Dict[str, str]):
        self.cfg = cfg
        self.client = self._init_client()

    def _init_client(self) -> OpenAI:
        """初始化 AI 客户端（优先使用数据库配置，其次 .env）"""
        api_key = get(self.cfg, "ai_api_key") or os.environ.get("OPENAI_API_KEY", "")
        base_url = get(self.cfg, "ai_base_url") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

        if not api_key:
            logger.warning("⚠️ 未发现 AI API Key（数据库和环境变量均为空）")

        return OpenAI(api_key=api_key, base_url=base_url)

    def summarize(self, news_list: List[Dict]) -> str:
        """使用大语言模型对抓取到的多条新闻进行总结并排版"""
        if not news_list:
            return "没有抓取到近期新闻内容。"

        api_key = get(self.cfg, "ai_api_key") or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return (
                "⚠️ 未发现 AI API Key。\n\n"
                "请在「系统设置」页面配置您的 API Key。\n\n"
                "抓取到的原生标题如下：\n"
                + "\n".join([f"- {item['title']}" for item in news_list])
            )

        model_name = get(self.cfg, "ai_model_name") or "gpt-4o-mini"
        temperature = get_float(self.cfg, "ai_temperature", 0.7)
        system_prompt = get(self.cfg, "ai_system_prompt") or "你是一个资深的 AI 科技主编。"
        max_news_for_ai = get_int(self.cfg, "fetch_max_news_for_ai", 15)

        logger.info(f"🧠 正在调用大模型 [{model_name}] 分析 {len(news_list)} 条新闻，请稍等...")

        top_news = news_list[:max_news_for_ai]
        context = ""
        for i, item in enumerate(top_news, 1):
            context += (
                f"新闻 {i}:\n"
                f"标题: {item['title']}\n"
                f"来源: {item['source']}\n"
                f"内容摘要: {item['summary']}\n"
                f"链接: {item['link']}\n\n"
            )

        prompt = f"""
        你是一位资深的 AI 科技媒体主编，现在要把今天最新的 {len(top_news)} 条科技/AI 资讯加工成爆款内容！

        要求如下：

        【第一步：内容筛选】
        从提供的资讯中挑选出 3-5 条最炸裂、最有话题性的新闻！

        【第二步：公众号爆款排版】（Markdown 格式）

        🎯 大标题要求：
        - 必须吸引眼球！用数字、感叹号、悬念式
        - 比如："今天这5条AI新闻，看完我睡不着了！"、"刚刚！AI圈发生了3件大事！"
        - 要让人情不自禁想点进来！

        📰 每条新闻要求：
        1. 小标题：要劲爆、要有冲突感
        2. 事件概述：2-3句话讲清楚核心
        3. 🔥 主编锐评：这是灵魂！要犀利、有深度、讲出对普通人的影响
           - 不要只说"这很重要"，要说"这意味着什么？对你我有什么影响？"
           - 可以适当用"细思极恐"、"细品"、"扎心了"之类的词

        【第三步：小红书爆款文案】

        📱 小红书文案要求（150字以内）：
        - 第一句必须炸！比如："谁懂啊！今天AI圈简直是炸锅了！"、"姐妹们！今天这5条新闻看完我直接清醒了！"
        - 多用 Emoji：🔥💥🚀🤯💡
        - 语言要口语化，像和闺蜜/兄弟聊天
        - 结尾要引导互动："你们怎么看？评论区聊聊！"、"点赞收藏，明天继续！"
        - 标签：#AI #人工智能 #科技早报 #ChatGPT #科技圈 #今天的瓜

        ---

        以下是今天的新闻素材：
        {context}
        """

        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = f"❌ AI 总结生成失败，报错信息: {e}"
            logger.error(error_msg)
            return error_msg

import feedparser
import os
import httpx
import logging
import time
from openai import OpenAI
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 解决某些 RSS 源抓取时的 SSL 证书验证问题
import ssl
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context


class NewsCollector:
    """AI 新闻采集系统主类（从数据库读取所有配置）"""

    def __init__(self):
        """初始化：从数据库加载配置，初始化 AI 客户端"""
        self.cfg = self._load_config_from_db()
        self.client = self._init_ai_client()

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------
    def _load_config_from_db(self) -> Dict[str, str]:
        """从 SystemConfig 表加载所有配置，返回 {key: value} 字典"""
        from database import SessionLocal
        from models import SystemConfig

        db = SessionLocal()
        try:
            rows = db.query(SystemConfig).all()
            cfg = {row.key: row.value for row in rows}
            logger.info(f"✅ 从数据库加载了 {len(cfg)} 条系统配置。")
            return cfg
        except Exception as e:
            logger.error(f"❌ 从数据库加载配置失败: {e}")
            return {}
        finally:
            db.close()

    # 便捷取值方法
    def _get(self, key: str, default: str = "") -> str:
        return self.cfg.get(key, default)

    def _get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.cfg.get(key, str(default)))
        except (ValueError, TypeError):
            return default

    def _get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.cfg.get(key, str(default)))
        except (ValueError, TypeError):
            return default

    def _get_bool(self, key: str, default: bool = False) -> bool:
        val = self.cfg.get(key, str(default))
        return val.lower() in ("true", "1", "yes")

    # ------------------------------------------------------------------
    # AI 客户端
    # ------------------------------------------------------------------
    def _init_ai_client(self) -> OpenAI:
        """初始化 AI 客户端（优先使用数据库配置，其次 .env）"""
        api_key = self._get("ai_api_key") or os.environ.get("OPENAI_API_KEY", "")
        base_url = self._get("ai_base_url") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

        if not api_key:
            logger.warning("⚠️ 未发现 AI API Key（数据库和环境变量均为空）")

        return OpenAI(api_key=api_key, base_url=base_url)

    # ------------------------------------------------------------------
    # RSS 采集
    # ------------------------------------------------------------------
    def fetch_rss_news(self) -> List[Dict]:
        """从数据库获取启用的 RSS 源并抓取新闻"""
        from database import SessionLocal
        from models import RssSource

        news_items: List[Dict] = []

        db = SessionLocal()
        try:
            rss_sources = db.query(RssSource).filter(RssSource.is_active == True).all()
            sources_list = [{"name": s.name, "url": s.url, "retry_times": s.retry_times} for s in rss_sources]
        except Exception as e:
            logger.error(f"❌ 从数据库读取 RSS 源失败: {e}")
            sources_list = []
        finally:
            db.close()

        if not sources_list:
            logger.warning("⚠️ 没有找到启用状态的 RSS 源，请检查数据库配置。")
            return news_items

        hours_ago = self._get_int("fetch_hours_ago", 48)
        max_summary_length = self._get_int("fetch_max_summary_length", 500)
        timeout = self._get_int("fetch_timeout", 10)
        time_threshold = datetime.now() - timedelta(hours=hours_ago)

        for source in sources_list:
            name = source.get("name", "Unknown")
            url = source.get("url")
            max_retries = source.get("retry_times", 3)

            if not url:
                logger.warning(f"⚠️ 跳过无效的 RSS 源: {name}")
                continue

            logger.info(f"📡 正在拉取资讯: {name}...")

            for attempt in range(max_retries):
                try:
                    response = httpx.get(
                        url,
                        timeout=timeout,
                        follow_redirects=True,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                                          "Chrome/120.0.0.0 Safari/537.36"
                        },
                    )
                    response.raise_for_status()

                    feed = feedparser.parse(response.content)

                    for entry in feed.entries:
                        pub_time = self._parse_publish_time(entry)
                        if not pub_time or pub_time > time_threshold:
                            news_items.append({
                                "title": entry.title,
                                "link": entry.link,
                                "summary": entry.get("summary", "")[:max_summary_length],
                                "source": name,
                            })

                    logger.info(f"✅ 成功从 {name} 抓取到新闻")
                    break

                except Exception as e:
                    logger.warning(f"⚠️ 抓取失败 {name} (尝试 {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                    else:
                        logger.error(f"❌ 抓取失败 {name}: 已达到最大重试次数")

        return news_items

    @staticmethod
    def _parse_publish_time(entry) -> Optional[datetime]:
        """解析新闻发布时间"""
        try:
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                return datetime.fromtimestamp(time.mktime(entry.published_parsed))
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # AI 内容生成
    # ------------------------------------------------------------------
    def summarize_with_ai(self, news_list: List[Dict]) -> str:
        """使用大语言模型对抓取到的多条新闻进行总结并排版"""
        if not news_list:
            return "没有抓取到近期新闻内容。"

        api_key = self._get("ai_api_key") or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return (
                "⚠️ 未发现 AI API Key。\n\n"
                "请在「系统设置」页面配置您的 API Key。\n\n"
                "抓取到的原生标题如下：\n"
                + "\n".join([f"- {item['title']}" for item in news_list])
            )

        model_name = self._get("ai_model_name") or "gpt-4o-mini"
        temperature = self._get_float("ai_temperature", 0.7)
        system_prompt = self._get("ai_system_prompt") or "你是一个资深的 AI 科技主编。"
        max_news_for_ai = self._get_int("fetch_max_news_for_ai", 15)

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

    # ------------------------------------------------------------------
    # 飞书推送
    # ------------------------------------------------------------------
    def push_to_feishu(self, content: str):
        """将内容推送到飞书自定义机器人 Webhook"""
        if not self._get_bool("push_feishu_enabled", True):
            logger.info("⚠️ 飞书推送已禁用，跳过。")
            return

        webhook_url = self._get("push_feishu_webhook") or os.environ.get("FEISHU_WEBHOOK_URL", "")
        if not webhook_url:
            logger.warning("⚠️ 未配置飞书 Webhook 地址，跳过飞书推送。")
            return

        logger.info("🚀 正在将今日新闻推送到飞书...")

        timeout = self._get_int("fetch_timeout", 10)
        headers = {"Content-Type": "application/json"}
        payload = {"msg_type": "text", "content": {"text": content}}

        try:
            response = httpx.post(webhook_url, json=payload, headers=headers, timeout=timeout)
            if response.status_code == 200:
                logger.info("✅ 成功推送到飞书！")
            else:
                logger.error(f"❌ 飞书推送失败: HTTP {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"❌ 飞书推送出错: {e}")

    # ------------------------------------------------------------------
    # 本地存档
    # ------------------------------------------------------------------
    def save_to_file(self, content: str) -> str:
        """保存内容到本地文件"""
        output_dir = self._get("output_archive_dir") or "archive"
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename_fmt = self._get("output_filename_format") or "AINews_{timestamp}.md"
        filename = filename_fmt.format(timestamp=timestamp)
        output_file = os.path.join(output_dir, filename)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"📁 最终生成的图文素材已保存至文件: {output_file}")
        return output_file

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def run(self):
        """运行完整的新闻采集流程"""
        logger.info("====== 自动化 AI 新闻助理启动 ======")

        # 第一步：抓取网页数据
        news = self.fetch_rss_news()
        logger.info(f"✅ 成功抓取到 {len(news)} 条最近的资讯。")
        logger.info("-" * 40)

        # 第二步：调用 AI 生成全套文案
        if len(news) > 0:
            ai_article = self.summarize_with_ai(news)
            print("\n" + ai_article)

            # 第三步：写入本地文件
            self.save_to_file(ai_article)

            # 第四步：推送到飞书
            logger.info("-" * 40)
            self.push_to_feishu(ai_article)
        else:
            logger.info("📭 今日暂无新鲜事。")


if __name__ == "__main__":
    collector = NewsCollector()
    collector.run()

import feedparser
import os
import json
import httpx
import logging
import yaml
import time
from openai import OpenAI
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv

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
    """AI 新闻采集系统主类"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """初始化配置和客户端"""
        self.config = self._load_config(config_path)
        load_dotenv()
        self.client = self._init_ai_client()
        
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"✅ 配置文件加载成功: {config_path}")
            return config
        except Exception as e:
            logger.error(f"❌ 配置文件加载失败: {e}")
            raise
    
    def _init_ai_client(self) -> OpenAI:
        """初始化 AI 客户端"""
        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        
        if not api_key:
            logger.warning("⚠️ 未发现 OPENAI_API_KEY 环境变量")
        
        return OpenAI(api_key=api_key, base_url=base_url)
    
    def fetch_rss_news(self) -> List[Dict]:
        """
        抓取 RSS 新闻源，过滤过去 hours_ago 小时内的新闻
        目前改为从 SQLite 数据库获取启用的 RSS 源
        """
        news_items = []
        
        # 从数据库中获取激活的 RSS 源
        from database import SessionLocal
        from models import RssSource
        
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

        fetch_config = self.config.get('fetch', {})
        hours_ago = fetch_config.get('hours_ago', 24)
        time_threshold = datetime.now() - timedelta(hours=hours_ago)
        
        for source in sources_list:
            name = source.get('name', 'Unknown')
            url = source.get('url')
            max_retries = source.get('retry_times', fetch_config.get('max_retries', 3))
            
            if not url:
                logger.warning(f"⚠️ 跳过无效的 RSS 源: {name}")
                continue
            
            logger.info(f"📡 正在拉取资讯: {name}...")
            
            for attempt in range(max_retries):
                try:
                    # 改用 httpx 先请求内容，避免 feedparser 内置请求的超时问题
                    response = httpx.get(
                        url,
                        timeout=fetch_config.get('timeout', 10),
                        follow_redirects=True,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        }
                    )
                    response.raise_for_status()
                    
                    # 解析 RSS 内容
                    feed = feedparser.parse(response.content)
                    
                    for entry in feed.entries:
                        pub_time = self._parse_publish_time(entry)
                        
                        if not pub_time or pub_time > time_threshold:
                            news_items.append({
                                "title": entry.title,
                                "link": entry.link,
                                "summary": entry.get("summary", "")[:fetch_config.get('max_summary_length', 500)],
                                "source": name
                            })
                    
                    logger.info(f"✅ 成功从 {name} 抓取到新闻")
                    break
                    
                except Exception as e:
                    logger.warning(f"⚠️ 抓取失败 {name} (尝试 {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)  # 重试前等待
                    else:
                        logger.error(f"❌ 抓取失败 {name}: 已达到最大重试次数")
            
        return news_items
    
    def _parse_publish_time(self, entry) -> Optional[datetime]:
        """解析新闻发布时间"""
        try:
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                import time
                return datetime.fromtimestamp(time.mktime(entry.published_parsed))
        except Exception:
            pass
        return None
    
    def summarize_with_ai(self, news_list: List[Dict]) -> str:
        """使用大语言模型对抓取到的多条新闻进行总结并排版"""
        if not news_list:
            return "没有抓取到近期新闻内容。"
        
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return "⚠️ 未发现 OPENAI_API_KEY 环境变量。\n\n由于缺少 API Key，无法调用大模型。\n请在代码或 .env 文件中设置您的 API Key。\n\n抓取到的原生标题如下：\n" + "\n".join([f"- {item['title']}" for item in news_list])
        
        ai_config = self.config.get('ai', {})
        fetch_config = self.config.get('fetch', {})
        
        logger.info(f"🧠 正在调用大模型分析 {len(news_list)} 条新闻，请稍等...")
        
        # 限制总数量，避免超出 Token
        top_news = news_list[:fetch_config.get('max_news_for_ai', 15)]
        context = ""
        for i, item in enumerate(top_news, 1):
            context += f"新闻 {i}:\n标题: {item['title']}\n来源: {item['source']}\n内容摘要: {item['summary']}\n链接: {item['link']}\n\n"
        
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
                model=ai_config.get('model_name', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": ai_config.get('system_prompt', '你是一个资深的 AI 科技主编。')},
                    {"role": "user", "content": prompt}
                ],
                temperature=ai_config.get('temperature', 0.7)
            )
            return response.choices[0].message.content
        except Exception as e:
            error_msg = f"❌ AI 总结生成失败，报错信息: {e}"
            logger.error(error_msg)
            return error_msg
    
    def push_to_feishu(self, content: str):
        """将内容推送到飞书自定义机器人 Webhook"""
        push_config = self.config.get('push', {})
        
        if not push_config.get('feishu_enabled', True):
            logger.info("⚠️ 飞书推送已禁用，跳过。")
            return
        
        webhook_url = os.environ.get("FEISHU_WEBHOOK_URL")
        if not webhook_url:
            logger.warning("⚠️ 未配置 FEISHU_WEBHOOK_URL 环境变量，跳过飞书推送。")
            return
        
        logger.info("🚀 正在将今日新闻推送到飞书...")
        
        headers = {"Content-Type": "application/json"}
        payload = {"msg_type": "text", "content": {"text": content}}
        
        try:
            response = httpx.post(
                webhook_url, 
                json=payload, 
                headers=headers, 
                timeout=self.config.get('fetch', {}).get('timeout', 10)
            )
            
            if response.status_code == 200:
                logger.info("✅ 成功推送到飞书！")
            else:
                logger.error(f"❌ 飞书推送失败: HTTP {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"❌ 飞书推送出错: {e}")
    
    def save_to_file(self, content: str) -> str:
        """保存内容到本地文件"""
        output_config = self.config.get('output', {})
        output_dir = output_config.get('archive_dir', 'archive')
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = output_config.get('filename_format', 'AINews_{timestamp}.md').format(timestamp=timestamp)
        output_file = os.path.join(output_dir, filename)
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"📁 最终生成的图文素材已保存至文件: {output_file}")
        return output_file
    
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

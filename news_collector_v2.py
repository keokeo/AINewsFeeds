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
        """
        news_items = []
        rss_sources = self.config.get('rss_sources', [])
        fetch_config = self.config.get('fetch', {})
        hours_ago = fetch_config.get('hours_ago', 24)
        time_threshold = datetime.now() - timedelta(hours=hours_ago)
        
        for source in rss_sources:
            name = source.get('name', 'Unknown')
            url = source.get('url')
            
            if not url:
                logger.warning(f"⚠️ 跳过无效的 RSS 源: {name}")
                continue
            
            logger.info(f"📡 正在拉取资讯: {name}...")
            
            for attempt in range(fetch_config.get('max_retries', 3)):
                try:
                    feed = feedparser.parse(url)
                    
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
                    logger.warning(f"⚠️ 抓取失败 {name} (尝试 {attempt + 1}/{fetch_config.get('max_retries', 3)}): {e}")
                    if attempt < fetch_config.get('max_retries', 3) - 1:
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
        你是一个资深的人工智能科技媒体编辑。我为你提供了今天最新抓取到的 {len(top_news)} 条科技/AI 相关的资讯。
        你的任务是将它们加工成适合发布在微信公众号和小红书的图文素材。
        
        要求如下：
        1. **内容筛选**：从提供的资讯中挑选出 3-5 条最有价值、最吸引人的新闻。
        2. **公众号排版**（Markdown 格式）：
           - 给今天的早报起一个吸引眼球的大标题。
           - 对每条选中的新闻，重写一个小标题，并简短总结事件核心。
           - 每条新闻后附上一句犀利的"主编点评"（解释其对普通人或行业的影响）。
        3. **小红书排版**：
           - 在文末另起一段，撰写专门用于发布小红书的 150 字以内的短文案。
           - 包含震惊或者诱导互动的第一句话。
           - 适当在文本中穿插 🚀🌟💡🔥 等 Emoji。
           - 末尾加上标签：#AI #人工智能 #科技早报 #ChatGPT 
        
        以下是抓取到的素材内容：
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

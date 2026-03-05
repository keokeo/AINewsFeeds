import feedparser
import os
import json
import httpx
from openai import OpenAI
from datetime import datetime, timedelta
import ssl
from dotenv import load_dotenv

# 解决某些 RSS 源抓取时的 SSL 证书验证问题
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# 加载 .env 文件中的环境变量 (例如存放 OPENAI_API_KEY)
load_dotenv()

# 初始化 AI 客户端
# 你可以在这里替换为你自己的 API Base URL (比如 DeepSeek, 智谱等兼容 OpenAI 格式的接口)
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY", "your-api-key-here"),
    base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
)

def fetch_rss_news(urls, hours_ago=24):
    """
    抓取 RSS 新闻源，过滤过去 hours_ago 小时内的新闻
    """
    news_items = []
    time_threshold = datetime.now() - timedelta(hours=hours_ago)
    
    for url in urls:
        print(f"📡 正在拉取资讯: {url}...")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # 解析时间
                pub_time = None
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        import time
                        pub_time = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                except Exception:
                    pass
                
                # 如果没解析出时间，或者时间在设定范围内，则收录
                if not pub_time or pub_time > time_threshold:
                    news_items.append({
                        "title": entry.title,
                        "link": entry.link,
                        "summary": entry.get("summary", "")[:500], # 限制摘要长度
                        "source": feed.feed.title if hasattr(feed, 'feed') and hasattr(feed.feed, 'title') else "Unknown"
                    })
        except Exception as e:
            print(f"❌ 抓取失败 {url}: {e}")
            
    return news_items

def summarize_with_ai(news_list):
    """
    使用大语言模型对抓取到的多条新闻进行总结并排版
    """
    if not news_list:
        return "没有抓取到近期新闻内容。"
        
    if os.environ.get("OPENAI_API_KEY") is None:
         return "⚠️ 未发现 OPENAI_API_KEY 环境变量。\n\n由于缺少 API Key，无法调用大模型。\n请在代码或 .env 文件中设置您的 API Key。\n\n抓取到的原生标题如下：\n" + "\n".join([f"- {item['title']}" for item in news_list])

    print(f"🧠 正在调用大模型分析 {len(news_list)} 条新闻，请稍等...")
    
    # 限制总数量，避免超出 Token，精选前 15 条传给大模型
    top_news = news_list[:15]
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
       - 每条新闻后附上一句犀利的“主编点评”（解释其对普通人或行业的影响）。
    3. **小红书排版**：
       - 在文末另起一段，撰写专门用于发布小红书的 150 字以内的短文案。
       - 包含震惊或者诱导互动的第一句话。
       - 适当在文本中穿插 🚀🌟💡🔥 等 Emoji。
       - 末尾加上标签：#AI #人工智能 #科技早报 #ChatGPT 
    
    以下是抓取到的素材内容：
    {context}
    """

    try:
        response = client.chat.completions.create(
            model=os.environ.get("MODEL_NAME", "gpt-4o-mini"), # 从环境变量读取模型名称(比如火山引擎的 Endpoint ID)
            messages=[
                {"role": "system", "content": "你是一个资深的 AI 科技主编，熟练掌握微信公众号和小红书的爆款写作技巧。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ AI 总结生成失败，报错信息: {e}"

def push_to_feishu(content):
    """
    将内容推送到飞书自定义机器人 Webhook
    """
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        print("⚠️ 未配置 FEISHU_WEBHOOK_URL 环境变量，跳过飞书推送。")
        return
    
    print("🚀 正在将今日新闻推送到飞书...")
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "msg_type": "text",
        "content": {
            "text": content
        }
    }
    try:
         # 因为网络请求可能会卡住，设置一个超时时间
         response = httpx.post(webhook_url, json=payload, headers=headers, timeout=10.0)
         if response.status_code == 200:
             print("✅ 成功推送到我的飞书！")
         else:
             print(f"❌ 飞书推送失败: HTTP {response.status_code} - {response.text}")
    except Exception as e:
         print(f"❌ 飞书推送出错: {e}")

if __name__ == "__main__":
    print("====== 自动化 AI 新闻助理启动 ======")
    
    # RSS 资讯源列表（以海外和国内著名的科技媒体为例）
    rss_sources = [
        # 海外媒体
        "https://techcrunch.com/category/artificial-intelligence/feed/", # TechCrunch AI专区
        "https://www.theverge.com/rss/index.xml", # The Verge
        "https://www.wired.com/feed/rss", # Wired
        "https://feeds.feedburner.com/TechCrunch/", # TechCrunch 全站
        "https://news.mit.edu/topic/artificial-intelligence2/feed", # MIT AI新闻
        
        # 国内媒体
        "https://www.solidot.org/index.rss", # Solidot 奇客资讯
        "https://36kr.com/feed", # 36氪
        "https://www.geekpark.net/rss", # 极客公园
        "https://www.ifanr.com/feed", # 爱范儿
        "https://www.qbitai.com/rss", # 量子位
        "https://www.jiqizhixin.com/rss", # 机器之心
        "https://sspai.com/feed", # 少数派
    ]
    
    # 第一步：抓取网页数据
    news = fetch_rss_news(rss_sources, hours_ago=48)
    print(f"✅ 成功抓取到 {len(news)} 条最近的资讯。")
    print("-" * 40)
    
    # 第二步：调用 AI 生成全套文案
    if len(news) > 0:
        ai_article = summarize_with_ai(news)
        print("\n" + ai_article)
        
        # 第三步：写入本地文件
        output_dir = "archive"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = os.path.join(output_dir, f"AINews_{timestamp}.md")
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(ai_article)
        print(f"\n📁 最终生成的图文素材已保存至文件: {output_file}")
        
        # 第四步：推送到飞书
        print("-" * 40)
        push_to_feishu(ai_article)
        
    else:
        print("📭 今日暂无新鲜事。")

"""
RSS 新闻采集服务
负责从 RSS 源抓取新闻数据
"""
import feedparser
import httpx
import logging
import time
import ssl
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from backend.core.config import get_int

logger = logging.getLogger(__name__)

# 解决某些 RSS 源抓取时的 SSL 证书验证问题
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context


class RssService:
    """RSS 新闻采集服务"""

    def fetch_news(self, cfg: Dict[str, str]) -> List[Dict]:
        """从数据库获取启用的 RSS 源并抓取新闻"""
        from backend.database import SessionLocal
        from backend.models import RssSource

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

        hours_ago = get_int(cfg, "fetch_hours_ago", 48)
        max_summary_length = get_int(cfg, "fetch_max_summary_length", 500)
        timeout = get_int(cfg, "fetch_timeout", 10)
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

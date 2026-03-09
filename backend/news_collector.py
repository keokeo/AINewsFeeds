"""
新闻采集工作流编排器
将各个服务串联成完整的采集流程
"""
import logging
from backend.core.config import load_config_from_db
from backend.services.rss import RssService
from backend.services.ai_content import AiContentService
from backend.services.notification import NotificationService
from backend.services.storage import StorageService

logger = logging.getLogger(__name__)


class NewsCollector:
    """AI 新闻采集系统 — 工作流编排器"""

    def __init__(self):
        self.cfg = load_config_from_db()
        self.rss_service = RssService()
        self.ai_service = AiContentService(self.cfg)
        self.notification_service = NotificationService()
        self.storage_service = StorageService()

    def run(self):
        """运行完整的新闻采集流程"""
        logger.info("====== 自动化 AI 新闻助理启动 ======")

        # 第一步：抓取网页数据
        news = self.rss_service.fetch_news(self.cfg)
        logger.info(f"✅ 成功抓取到 {len(news)} 条最近的资讯。")
        logger.info("-" * 40)

        # 第二步：调用 AI 生成全套文案
        if len(news) > 0:
            ai_article = self.ai_service.summarize(news)
            print("\n" + ai_article)

            # 第三步：写入本地文件
            self.storage_service.save_to_file(self.cfg, ai_article)

            # 第四步：推送到飞书
            logger.info("-" * 40)
            self.notification_service.push_to_feishu(self.cfg, ai_article)
        else:
            logger.info("📭 今日暂无新鲜事。")


if __name__ == "__main__":
    collector = NewsCollector()
    collector.run()

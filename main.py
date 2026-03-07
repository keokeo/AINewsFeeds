"""
AI 新闻自动采集与同步系统 - FastAPI 应用入口
"""
import yaml
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, SessionLocal
from models import Base, RssSource, SystemConfig
from routers import rss, settings, tasks
from scheduler import scheduler, load_schedule_from_db

logger = logging.getLogger(__name__)


def seed_rss_sources_from_config(config_path: str = "config.yaml"):
    """
    从 config.yaml 中读取 RSS 源配置，并将其导入到数据库中。
    仅在数据库表为空时执行（首次初始化）。
    """
    db = SessionLocal()
    try:
        existing_count = db.query(RssSource).count()
        if existing_count > 0:
            logger.info(f"📦 数据库中已有 {existing_count} 条 RSS 源，跳过初始化导入。")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        rss_sources = config.get("rss_sources", [])
        if not rss_sources:
            logger.warning("⚠️ config.yaml 中未找到 rss_sources 配置。")
            return

        for source in rss_sources:
            db_source = RssSource(
                name=source.get("name", "Unknown"),
                url=source.get("url", ""),
                is_active=True,
                category="海外媒体" if any(
                    kw in source.get("name", "")
                    for kw in ["TechCrunch", "Verge", "Wired", "MIT"]
                ) else "国内媒体",
            )
            db.add(db_source)

        db.commit()
        logger.info(f"✅ 成功从 config.yaml 导入 {len(rss_sources)} 条 RSS 源到数据库。")
    except FileNotFoundError:
        logger.warning("⚠️ 未找到 config.yaml 文件，跳过初始化导入。")
    except Exception as e:
        logger.error(f"❌ 导入 RSS 源失败: {e}")
        db.rollback()
    finally:
        db.close()


def seed_system_config(config_path: str = "config.yaml"):
    """
    从 config.yaml 和 .env 中读取系统配置，并将其导入到数据库中。
    仅在数据库表为空时执行（首次初始化）。
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()

    db = SessionLocal()
    try:
        existing_count = db.query(SystemConfig).count()
        if existing_count > 0:
            logger.info(f"📦 数据库中已有 {existing_count} 条系统配置，跳过初始化导入。")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        ai_config = config.get("ai", {})
        fetch_config = config.get("fetch", {})
        push_config = config.get("push", {})
        output_config = config.get("output", {})

        # 默认配置项列表
        defaults = [
            # AI 模型配置
            ("ai_api_key", os.environ.get("OPENAI_API_KEY", ""), "ai", "大模型 API Key"),
            ("ai_base_url", os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"), "ai", "大模型 API 地址"),
            ("ai_model_name", ai_config.get("model_name", "gpt-4o-mini"), "ai", "模型名称"),
            ("ai_temperature", str(ai_config.get("temperature", 0.7)), "ai", "温度参数（0-1，越高越有创意）"),
            ("ai_system_prompt", ai_config.get("system_prompt", ""), "ai", "系统提示词"),
            # 采集设置
            ("fetch_hours_ago", str(fetch_config.get("hours_ago", 48)), "fetch", "抓取过去多少小时内的新闻"),
            ("fetch_max_summary_length", str(fetch_config.get("max_summary_length", 500)), "fetch", "每条新闻摘要最大长度"),
            ("fetch_max_news_for_ai", str(fetch_config.get("max_news_for_ai", 15)), "fetch", "最多传给 AI 分析的新闻数量"),
            ("fetch_timeout", str(fetch_config.get("timeout", 10)), "fetch", "请求超时时间（秒）"),
            # 推送设置
            ("push_feishu_enabled", str(push_config.get("feishu_enabled", True)), "push", "是否推送到飞书"),
            ("push_feishu_webhook", os.environ.get("FEISHU_WEBHOOK_URL", ""), "push", "飞书 Webhook 地址"),
            ("push_wechat_enabled", str(push_config.get("wechat_enabled", False)), "push", "是否推送到微信公众号"),
            # 输出设置
            ("output_archive_dir", output_config.get("archive_dir", "archive"), "output", "本地存档目录"),
            ("output_filename_format", output_config.get("filename_format", "AINews_{timestamp}.md"), "output", "存档文件名格式"),
            # 定时任务设置
            ("schedule_enabled", "False", "schedule", "是否启用定时采集"),
            ("schedule_time", "08:00", "schedule", "定时执行时间（24小时制，多个用逗号分隔，如 08:00,18:00）"),
        ]

        for key, value, category, description in defaults:
            db.add(SystemConfig(key=key, value=str(value), category=category, description=description))

        db.commit()
        logger.info(f"✅ 成功初始化 {len(defaults)} 条系统配置到数据库。")
    except FileNotFoundError:
        logger.warning("⚠️ 未找到 config.yaml 文件，跳过系统配置初始化。")
    except Exception as e:
        logger.error(f"❌ 初始化系统配置失败: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时：创建数据库表 + 导入初始数据
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据库表结构已就绪。")
    seed_rss_sources_from_config()
    seed_system_config()

    # 启动定时任务调度器
    scheduler.start()
    load_schedule_from_db()
    logger.info("⏰ 定时任务调度器已启动。")

    yield

    # 关闭时：停止调度器并清理资源
    scheduler.shutdown(wait=False)
    logger.info("👋 应用已关闭，调度器已停止。")


app = FastAPI(
    title="AI 新闻自动采集与同步系统",
    description="提供 RSS 源管理、内容采集、AI 加工和多平台推送的一站式 API 服务",
    version="1.1.0",
    lifespan=lifespan,
)

# 配置 CORS 中间件（允许前端跨域调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(rss.router)
app.include_router(settings.router)
app.include_router(tasks.router)


@app.get("/", tags=["系统"])
def root():
    """系统根路径，返回基本信息"""
    return {
        "system": "AI 新闻自动采集与同步系统",
        "version": "1.1.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health", tags=["系统"])
def health_check():
    """健康检查接口"""
    return {"status": "ok"}

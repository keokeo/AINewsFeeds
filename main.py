"""
AI 新闻自动采集与同步系统 - FastAPI 应用入口
"""
import yaml
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, SessionLocal
from models import Base, RssSource
from routers import rss

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时：创建数据库表 + 导入初始数据
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据库表结构已就绪。")
    seed_rss_sources_from_config()
    yield
    # 关闭时：清理资源（如需要）
    logger.info("👋 应用已关闭。")


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

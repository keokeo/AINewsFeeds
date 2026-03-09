"""
AI 新闻自动采集与同步系统 - FastAPI 应用入口
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import engine
from backend.models import Base
from backend.core.init_db import seed_rss_sources, seed_system_config
from backend.routers import rss, settings, tasks
from backend.scheduler import scheduler, load_schedule_from_db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时：创建数据库表 + 导入初始数据
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据库表结构已就绪。")
    seed_rss_sources()
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

"""
任务管理路由
提供手动触发采集生成的 API
"""
import logging
from fastapi import APIRouter, BackgroundTasks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["任务管理"])


def _run_collection_task():
    """后台执行新闻采集 + AI 生成的完整流程"""
    try:
        from news_collector_v2 import NewsCollector
        collector = NewsCollector()
        collector.run()
    except Exception as e:
        logger.error(f"❌ 后台采集任务执行失败: {e}")


@router.post("/trigger", summary="手动触发采集生成任务")
def trigger_collection(background_tasks: BackgroundTasks):
    """手动触发一次完整的新闻采集 + AI 生成流程（后台异步执行）"""
    background_tasks.add_task(_run_collection_task)
    return {"message": "✅ 采集生成任务已触发，正在后台执行中..."}

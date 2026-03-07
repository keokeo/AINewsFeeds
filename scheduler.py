"""
定时任务调度模块
使用 APScheduler 实现定时自动采集新闻并生成内容
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# 全局调度器实例
scheduler = AsyncIOScheduler()

JOB_ID = "news_collection_job"


def _run_collection_job():
    """执行新闻采集任务（同步，由 APScheduler 在线程池中调用）"""
    try:
        from news_collector import NewsCollector
        logger.info("⏰ [定时任务] 开始执行自动新闻采集...")
        collector = NewsCollector()
        collector.run()
        logger.info("⏰ [定时任务] 自动新闻采集完成！")
    except Exception as e:
        logger.error(f"⏰ [定时任务] 执行失败: {e}")


def load_schedule_from_db():
    """
    从数据库中读取 schedule_enabled 和 schedule_time，
    动态注册或移除定时任务。
    """
    from database import SessionLocal
    from models import SystemConfig

    db = SessionLocal()
    try:
        rows = db.query(SystemConfig).filter(
            SystemConfig.key.in_(["schedule_enabled", "schedule_time"])
        ).all()
        cfg = {row.key: row.value for row in rows}
    except Exception as e:
        logger.error(f"❌ 读取定时任务配置失败: {e}")
        return
    finally:
        db.close()

    enabled = cfg.get("schedule_enabled", "False").lower() in ("true", "1", "yes")
    time_str = cfg.get("schedule_time", "08:00")

    # 先移除旧任务（如果有）
    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)
        logger.info("⏰ 已移除旧的定时任务。")

    if not enabled:
        logger.info("⏰ 定时任务已禁用。")
        return

    # 解析时间字符串，支持多个时间点用逗号分隔，如 "08:00,18:00"
    times = [t.strip() for t in time_str.split(",") if t.strip()]

    for i, t in enumerate(times):
        try:
            hour, minute = t.split(":")
            job_id = f"{JOB_ID}_{i}" if len(times) > 1 else JOB_ID
            # 先移除同名旧任务
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)

            scheduler.add_job(
                _run_collection_job,
                trigger=CronTrigger(hour=int(hour), minute=int(minute)),
                id=job_id,
                replace_existing=True,
                name=f"自动采集 ({t})",
            )
            logger.info(f"⏰ 已注册定时任务: 每天 {t} 执行新闻采集。")
        except Exception as e:
            logger.warning(f"⚠️ 解析定时时间 '{t}' 失败: {e}")

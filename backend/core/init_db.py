"""
数据库初始化与种子数据导入
从 config.yaml 和 .env 读取初始配置，仅在数据库表为空时执行。
"""
import os
import yaml
import logging

logger = logging.getLogger(__name__)

# config.yaml 的默认路径（相对于 backend/ 目录）
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(_BACKEND_DIR, "config.yaml")


def seed_rss_sources(config_path: str = DEFAULT_CONFIG_PATH):
    """
    从 config.yaml 中读取 RSS 源配置，并将其导入到数据库中。
    仅在数据库表为空时执行（首次初始化）。
    """
    from backend.database import SessionLocal
    from backend.models import RssSource

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


def seed_system_config(config_path: str = DEFAULT_CONFIG_PATH):
    """
    从 config.yaml 和 .env 中读取系统配置，并将其导入到数据库中。
    仅在数据库表为空时执行（首次初始化）。
    """
    from dotenv import load_dotenv
    load_dotenv()

    from backend.database import SessionLocal
    from backend.models import SystemConfig

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

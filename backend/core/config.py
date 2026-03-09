"""
数据库配置辅助 — 从数据库加载配置的统一接口
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def load_config_from_db() -> Dict[str, str]:
    """从 SystemConfig 表加载所有配置，返回 {key: value} 字典"""
    from backend.database import SessionLocal
    from backend.models import SystemConfig

    db = SessionLocal()
    try:
        rows = db.query(SystemConfig).all()
        cfg = {row.key: row.value for row in rows}
        logger.info(f"✅ 从数据库加载了 {len(cfg)} 条系统配置。")
        return cfg
    except Exception as e:
        logger.error(f"❌ 从数据库加载配置失败: {e}")
        return {}
    finally:
        db.close()


# ---- 便捷取值函数 ----

def get(cfg: Dict[str, str], key: str, default: str = "") -> str:
    return cfg.get(key, default)


def get_int(cfg: Dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(cfg.get(key, str(default)))
    except (ValueError, TypeError):
        return default


def get_float(cfg: Dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(cfg.get(key, str(default)))
    except (ValueError, TypeError):
        return default


def get_bool(cfg: Dict[str, str], key: str, default: bool = False) -> bool:
    val = cfg.get(key, str(default))
    return val.lower() in ("true", "1", "yes")

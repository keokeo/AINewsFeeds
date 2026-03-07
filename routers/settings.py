"""
系统配置管理路由
提供 AI 参数、采集设置、推送设置的读取和修改 API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Optional
from pydantic import BaseModel

from database import get_db
from models import SystemConfig

router = APIRouter(prefix="/api/settings", tags=["系统配置"])


class ConfigUpdateRequest(BaseModel):
    """批量更新配置的请求体"""
    configs: Dict[str, str]


class ConfigItemResponse(BaseModel):
    """单个配置项的响应"""
    key: str
    value: str
    category: str
    description: str

    model_config = {"from_attributes": True}


@router.get("/", summary="获取所有系统配置")
def get_all_settings(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取所有系统配置，可按分类筛选"""
    query = db.query(SystemConfig)
    if category:
        query = query.filter(SystemConfig.category == category)

    configs = query.order_by(SystemConfig.category, SystemConfig.key).all()

    # 按分类分组返回
    result: Dict[str, Dict] = {}
    for c in configs:
        if c.category not in result:
            result[c.category] = {}
        result[c.category][c.key] = {
            "value": c.value,
            "description": c.description,
        }
    return result


@router.get("/{key}", response_model=ConfigItemResponse, summary="获取单个配置项")
def get_setting(
    key: str,
    db: Session = Depends(get_db),
):
    """根据键名获取单个配置项"""
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not config:
        return {"key": key, "value": "", "category": "unknown", "description": "未找到此配置"}
    return config


@router.put("/", summary="批量更新配置")
def update_settings(
    request: ConfigUpdateRequest,
    db: Session = Depends(get_db),
):
    """批量更新多个配置项"""
    updated = []
    for key, value in request.configs.items():
        config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if config:
            config.value = value
            updated.append(key)

    db.commit()

    # 如果更新了定时任务相关的配置，立即重新加载调度计划
    schedule_keys = {"schedule_enabled", "schedule_time"}
    if schedule_keys & set(updated):
        try:
            from scheduler import load_schedule_from_db
            load_schedule_from_db()
        except Exception as e:
            logger.warning(f"⚠️ 重新加载定时任务配置失败: {e}")

    return {"message": f"成功更新 {len(updated)} 项配置", "updated_keys": updated}


@router.put("/{key}", summary="更新单个配置项")
def update_setting(
    key: str,
    value: str,
    db: Session = Depends(get_db),
):
    """更新单个配置项的值"""
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if not config:
        # 如果不存在则创建
        config = SystemConfig(key=key, value=value, category="custom", description="用户自定义配置")
        db.add(config)
    else:
        config.value = value

    db.commit()
    db.refresh(config)
    return {"key": config.key, "value": config.value, "message": "配置已更新"}

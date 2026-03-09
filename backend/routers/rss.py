"""
RSS 源管理路由
提供 RSS 源的增删改查 API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.models import RssSource
from backend.schemas import RssSourceCreate, RssSourceUpdate, RssSourceResponse

router = APIRouter(prefix="/api/rss", tags=["RSS 源管理"])


@router.get("/sources", response_model=List[RssSourceResponse], summary="获取 RSS 源列表")
def get_rss_sources(
    is_active: Optional[bool] = Query(None, description="按启用状态筛选"),
    category: Optional[str] = Query(None, description="按分类筛选"),
    keyword: Optional[str] = Query(None, description="按名称关键词搜索"),
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(100, ge=1, le=500, description="每页数量"),
    db: Session = Depends(get_db),
):
    """获取所有 RSS 源列表，支持筛选和分页"""
    query = db.query(RssSource)

    if is_active is not None:
        query = query.filter(RssSource.is_active == is_active)
    if category:
        query = query.filter(RssSource.category == category)
    if keyword:
        query = query.filter(RssSource.name.contains(keyword))

    sources = query.order_by(RssSource.created_at.desc()).offset(skip).limit(limit).all()
    return sources


@router.post("/sources", response_model=RssSourceResponse, status_code=201, summary="新增 RSS 源")
def create_rss_source(
    source: RssSourceCreate,
    db: Session = Depends(get_db),
):
    """新增一个 RSS 源"""
    # 检查 URL 是否已存在
    existing = db.query(RssSource).filter(RssSource.url == source.url).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"该 RSS 源地址已存在（ID: {existing.id}, 名称: {existing.name}）")

    db_source = RssSource(**source.model_dump())
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


@router.get("/sources/{source_id}", response_model=RssSourceResponse, summary="获取单个 RSS 源详情")
def get_rss_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    """根据 ID 获取单个 RSS 源的详情"""
    source = db.query(RssSource).filter(RssSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="RSS 源不存在")
    return source


@router.put("/sources/{source_id}", response_model=RssSourceResponse, summary="更新 RSS 源")
def update_rss_source(
    source_id: int,
    source_update: RssSourceUpdate,
    db: Session = Depends(get_db),
):
    """更新指定 ID 的 RSS 源配置"""
    source = db.query(RssSource).filter(RssSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="RSS 源不存在")

    # 如果更新了 URL，检查新 URL 是否和其他记录冲突
    update_data = source_update.model_dump(exclude_unset=True)
    if "url" in update_data:
        existing = db.query(RssSource).filter(
            RssSource.url == update_data["url"],
            RssSource.id != source_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"该 URL 已被其他 RSS 源使用（ID: {existing.id}）")

    for key, value in update_data.items():
        setattr(source, key, value)

    db.commit()
    db.refresh(source)
    return source


@router.delete("/sources/{source_id}", summary="删除 RSS 源")
def delete_rss_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    """删除指定 ID 的 RSS 源"""
    source = db.query(RssSource).filter(RssSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="RSS 源不存在")

    db.delete(source)
    db.commit()
    return {"message": f"RSS 源 '{source.name}' 已成功删除", "id": source_id}

"""
Pydantic 数据校验模型（请求/响应 Schema）
"""
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse


class RssSourceBase(BaseModel):
    """RSS 源基础字段"""
    name: str
    url: str
    is_active: bool = True
    category: str = "默认"
    retry_times: int = 3
    fetch_interval: int = 60
    description: str = ""

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("无效的 URL 格式，请提供完整的地址（如 https://example.com/rss）")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("名称不能为空")
        return v.strip()


class RssSourceCreate(RssSourceBase):
    """新建 RSS 源时的请求体"""
    pass


class RssSourceUpdate(BaseModel):
    """更新 RSS 源时的请求体（所有字段可选）"""
    name: Optional[str] = None
    url: Optional[str] = None
    is_active: Optional[bool] = None
    category: Optional[str] = None
    retry_times: Optional[int] = None
    fetch_interval: Optional[int] = None
    description: Optional[str] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            parsed = urlparse(v)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("无效的 URL 格式")
        return v


class RssSourceResponse(RssSourceBase):
    """RSS 源的返回数据"""
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

"""
数据库 ORM 模型定义
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func

from database import Base


class RssSource(Base):
    """RSS 资讯源表"""
    __tablename__ = "rss_sources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="RSS 源名称")
    url = Column(String(500), unique=True, nullable=False, comment="RSS 源地址")
    is_active = Column(Boolean, default=True, comment="是否启用")
    category = Column(String(50), default="默认", comment="分类（如：海外媒体、国内媒体）")
    retry_times = Column(Integer, default=3, comment="失败重试次数")
    fetch_interval = Column(Integer, default=60, comment="采集间隔（分钟）")
    description = Column(Text, default="", comment="备注说明")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<RssSource(id={self.id}, name='{self.name}', active={self.is_active})>"

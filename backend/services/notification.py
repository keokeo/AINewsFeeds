"""
通知推送服务
负责将生成的内容推送到各平台（飞书等）
"""
import os
import httpx
import logging
from typing import Dict

from backend.core.config import get, get_int, get_bool

logger = logging.getLogger(__name__)


class NotificationService:
    """通知推送服务"""

    def push_to_feishu(self, cfg: Dict[str, str], content: str):
        """将内容推送到飞书自定义机器人 Webhook"""
        if not get_bool(cfg, "push_feishu_enabled", True):
            logger.info("⚠️ 飞书推送已禁用，跳过。")
            return

        webhook_url = get(cfg, "push_feishu_webhook") or os.environ.get("FEISHU_WEBHOOK_URL", "")
        if not webhook_url:
            logger.warning("⚠️ 未配置飞书 Webhook 地址，跳过飞书推送。")
            return

        logger.info("🚀 正在将今日新闻推送到飞书...")

        timeout = get_int(cfg, "fetch_timeout", 10)
        headers = {"Content-Type": "application/json"}
        payload = {"msg_type": "text", "content": {"text": content}}

        try:
            response = httpx.post(webhook_url, json=payload, headers=headers, timeout=timeout)
            if response.status_code == 200:
                logger.info("✅ 成功推送到飞书！")
            else:
                logger.error(f"❌ 飞书推送失败: HTTP {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"❌ 飞书推送出错: {e}")

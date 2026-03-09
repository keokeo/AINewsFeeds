"""
本地存档服务
负责将生成的内容保存到本地文件
"""
import os
import logging
from datetime import datetime
from typing import Dict

from backend.core.config import get

logger = logging.getLogger(__name__)


class StorageService:
    """本地文件存档服务"""

    def save_to_file(self, cfg: Dict[str, str], content: str) -> str:
        """保存内容到本地文件"""
        output_dir = get(cfg, "output_archive_dir") or "archive"
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename_fmt = get(cfg, "output_filename_format") or "AINews_{timestamp}.md"
        filename = filename_fmt.format(timestamp=timestamp)
        output_file = os.path.join(output_dir, filename)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"📁 最终生成的图文素材已保存至文件: {output_file}")
        return output_file

import time
import hashlib
from typing import Dict, Optional
from loguru import logger


class QRCodeDeduplicator:
    """基于时间窗口的二维码去重器

    - 指定时间窗口内相同内容视为重复
    - 超出时间窗口后视为新二维码，允许重新触发
    - 自动清理60秒前的历史记录，控制内存占用
    """

    def __init__(self, window_seconds: int = 30):
        self._WINDOW_SECONDS = window_seconds
        self._history: Dict[str, float] = {}      # hash -> first_seen_time
        self._sent: Dict[str, float] = {}          # hash -> sent_time
        self._total_seen = 0
        self._total_sent = 0

    def is_duplicate(self, content: str) -> bool:
        """检查二维码内容是否为重复（30秒窗口内出现过）

        首次出现返回 False，并在窗口内再次出现返回 True。
        """
        content_hash = self._hash_content(content)
        now = time.time()

        if content_hash in self._history:
            last_seen = self._history[content_hash]
            if now - last_seen < self._WINDOW_SECONDS:
                logger.info(f"【去重】30秒窗口内重复二维码 [{content[:60]}...]，跳过")
                return True
            else:
                logger.info(f"【去重】二维码已超出30秒窗口 [{content[:60]}...]，允许重新触发")

        # 新二维码或超出窗口，记录并返回非重复
        self._history[content_hash] = now
        self._total_seen += 1
        self._cleanup(now)
        return False

    def mark_sent(self, content: str) -> None:
        """标记二维码已成功发送"""
        content_hash = self._hash_content(content)
        self._sent[content_hash] = time.time()
        self._total_sent += 1
        logger.info(f"【去重】二维码已标记为已发送 [{content[:60]}...]")

    def was_sent(self, content: str) -> bool:
        """查询二维码是否曾被发送过"""
        content_hash = self._hash_content(content)
        return content_hash in self._sent

    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _cleanup(self, now: float) -> None:
        """清理超过60秒的历史记录，防止内存膨胀"""
        threshold = now - self._WINDOW_SECONDS * 2
        expired = [h for h, ts in self._history.items() if ts < threshold]
        for h in expired:
            del self._history[h]

        # 同时清理过期的发送记录
        sent_expired = [h for h, ts in self._sent.items() if ts < threshold]
        for h in sent_expired:
            del self._sent[h]

        if expired or sent_expired:
            logger.debug(f"【去重】已清理 {len(expired)} 条过期检测记录, {len(sent_expired)} 条发送记录")

    def clear(self) -> None:
        """重置所有去重状态（引擎重启时调用）"""
        self._history.clear()
        self._sent.clear()
        self._total_seen = 0
        self._total_sent = 0
        logger.info("【去重】去重记录已重置")

    @property
    def stats(self) -> dict:
        return {
            "seen": self._total_seen,
            "sent": self._total_sent,
            "history_size": len(self._history),
        }
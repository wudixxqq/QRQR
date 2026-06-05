import base64
import hashlib
import io
from pathlib import Path
from typing import Optional
import requests
from PIL import Image, ImageGrab
from loguru import logger


# 企业微信图片消息限制：不超过 2MB
_MAX_IMAGE_BYTES = 2 * 1024 * 1024


def image_bytes_to_base64(image_data: bytes) -> str:
    """将图片二进制数据转换为 base64 字符串"""
    return base64.b64encode(image_data).decode("utf-8")


def calculate_md5(data: bytes) -> str:
    """计算数据的 MD5 哈希值"""
    return hashlib.md5(data).hexdigest()


class WeWorkWebhookBot:
    """企业微信 Webhook 机器人消息发送器

    通过 Webhook URL 向企业微信群聊发送文本和图片消息。
    完全替代原 WeChatBot 的微信自动化方案，使用纯 API 接口。
    """

    def __init__(self, webhook_url: str = ""):
        """
        Args:
            webhook_url: 企业微信机器人 Webhook URL
                        格式: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
        """
        self._webhook_url = webhook_url
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ============================================================
    # 对外接口（与原 WeChatBot 保持一致）
    # ============================================================

    def send_image(self, image_bytes: bytes) -> bool:
        """发送图片消息，附带签到提示文本

        Args:
            image_bytes: 图片二进制数据（PNG/JPEG 等格式）

        Returns:
            True 表示发送成功，False 表示失败
        """
        if not self._webhook_url:
            logger.error("【企业微信】webhook_url 未配置，无法发送图片")
            return False

        if len(image_bytes) > _MAX_IMAGE_BYTES:
            logger.warning(f"【企业微信】图片大小 {len(image_bytes)} 超过 2MB，可能发送失败")

        # 先发送签到提示文本
        self.send_text("开始签到，尽快打卡")

        try:
            img_base64 = image_bytes_to_base64(image_bytes)
            img_md5 = calculate_md5(image_bytes)

            payload = {
                "msgtype": "image",
                "image": {
                    "base64": img_base64,
                    "md5": img_md5,
                },
            }

            resp = self._session.post(self._webhook_url, json=payload, timeout=15)
            result = resp.json()

            if result.get("errcode") == 0:
                logger.info(f"【企业微信】图片发送成功 ({len(image_bytes)} bytes)")
                return True
            else:
                logger.error(f"【企业微信】图片发送失败: {result.get('errmsg', result)}")
                return False

        except requests.exceptions.Timeout:
            logger.error("【企业微信】图片发送超时")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"【企业微信】图片发送网络异常: {e}")
            return False
        except Exception as e:
            logger.error(f"【企业微信】图片发送异常: {e}")
            return False

    def send_text(self, text: str) -> bool:
        """发送文本消息

        Args:
            text: 文本内容，最长不超过 2048 个字节

        Returns:
            True 表示发送成功，False 表示失败
        """
        if not self._webhook_url:
            logger.error("【企业微信】webhook_url 未配置，无法发送文本")
            return False

        if len(text.encode("utf-8")) > 2048:
            logger.warning("【企业微信】文本内容超过 2048 字节，可能被截断")

        try:
            payload = {
                "msgtype": "text",
                "text": {"content": text},
            }

            resp = self._session.post(self._webhook_url, json=payload, timeout=15)
            result = resp.json()

            if result.get("errcode") == 0:
                logger.info(f"【企业微信】文本发送成功: {text[:60]}...")
                return True
            else:
                logger.error(f"【企业微信】文本发送失败: {result.get('errmsg', result)}")
                return False

        except requests.exceptions.Timeout:
            logger.error("【企业微信】文本发送超时")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"【企业微信】文本发送网络异常: {e}")
            return False
        except Exception as e:
            logger.error(f"【企业微信】文本发送异常: {e}")
            return False

    def send_clipboard_image(self) -> bool:
        """读取剪贴板图片并发送

        Returns:
            True 表示发送成功，False 表示失败
        """
        try:
            img = ImageGrab.grabclipboard()
            if img is None:
                logger.error("【企业微信】剪贴板中没有图片")
                return False
            if isinstance(img, list):
                logger.error("【企业微信】剪贴板包含文件列表，非图片")
                return False

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_bytes = buf.getvalue()

            logger.info(f"【企业微信】从剪贴板读取图片: {len(image_bytes)} bytes")
            return self.send_image(image_bytes)

        except Exception as e:
            logger.error(f"【企业微信】读取剪贴板图片异常: {e}")
            return False

    def send_screenshot_file(self, file_path: str) -> bool:
        """读取截图文件并发送

        Args:
            file_path: 截图文件路径

        Returns:
            True 表示发送成功，False 表示失败
        """
        path = Path(file_path)
        if not path.is_file():
            logger.error(f"【企业微信】截图文件不存在: {file_path}")
            return False

        try:
            with open(file_path, "rb") as f:
                image_bytes = f.read()
            logger.info(f"【企业微信】读取截图文件: {file_path} ({len(image_bytes)} bytes)")
            return self.send_image(image_bytes)

        except Exception as e:
            logger.error(f"【企业微信】读取截图文件异常: {e}")
            return False

    def reload(self, webhook_url: str) -> None:
        """热更新 webhook URL（配置变更时调用）"""
        self._webhook_url = webhook_url
        logger.info("【企业微信】Webhook URL 已更新")


# 以下为兼容性导出（供外部脚本直接调用）
def send_to_wechat_webhook(webhook_url: str, base64_data: str, md5_value: str) -> bool:
    """发送 base64 图片到企业微信 Webhook（兼容旧接口）"""
    bot = WeWorkWebhookBot(webhook_url)
    try:
        image_bytes = base64.b64decode(base64_data)
        return bot.send_image(image_bytes)
    except Exception as e:
        logger.error(f"企业微信发送失败: {e}")
        return False


def get_clipboard_image():
    """读取剪贴板图片（兼容旧接口）"""
    try:
        import win32clipboard

        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
            data = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
            win32clipboard.CloseClipboard()
            image = ImageGrab.grabclipboard()
            if image:
                return image
        win32clipboard.CloseClipboard()
    except Exception as e:
        logger.error(f"读取剪贴板失败: {e}")
    return None


def image_to_base64(image):
    """将 PIL Image 转换为 base64（兼容旧接口）"""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_data = buffered.getvalue()
    img_base64 = base64.b64encode(img_data).decode("utf-8")
    return img_base64, img_data


def main():
    """命令行测试入口"""
    WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY_HERE"

    print("正在读取剪贴板图片...")
    image = get_clipboard_image()

    if not image:
        print("剪贴板中没有图片！")
        return

    print("正在处理图片...")
    img_base64, img_data = image_to_base64(image)
    img_md5 = calculate_md5(img_data)

    print(f"图片大小: {len(img_data)} 字节")

    if len(img_data) > _MAX_IMAGE_BYTES:
        print("警告：图片超过2MB，可能发送失败！")

    print("正在发送到企业微信...")
    bot = WeWorkWebhookBot(WEBHOOK_URL)
    result = bot.send_image(img_data)
    print(f"发送结果: {'成功' if result else '失败'}")


if __name__ == "__main__":
    main()
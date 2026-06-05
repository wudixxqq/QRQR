"""企业微信 Webhook 机器人消息发送模块

完全替代原 WeChatBot 的微信自动化方案。
所有核心实现在 send_clipboard_image.py 的 WeWorkWebhookBot 类中。
"""

from send_clipboard_image import WeWorkWebhookBot

# 为向后兼容，保留 WeChatBot 别名
WeChatBot = WeWorkWebhookBot
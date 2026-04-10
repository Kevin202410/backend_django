# app_mqtt/redis_listener.py
import redis
import json
import threading
from django.conf import settings
from app_mqtt.utils import get_logger
from app_mqtt.mqtt_client import mqtt_client

logger = get_logger(__name__)

class RedisListener(threading.Thread):
    def __init__(self):
        super().__init__()
        self.redis_client = redis.from_url(
            settings.REDIS_URL,
            db=settings.MQTT_REDIS_DB,
            decode_responses=True
        )
        self.list_key = settings.MQTT_REDIS_LIST_KEY
        self.running = True
        self.daemon = True

    def run(self):
        logger.info("Redis 监听器已启动，等待消息...")
        while self.running:
            try:
                # 阻塞弹出列表元素，超时1秒
                result = self.redis_client.blpop(self.list_key, timeout=1)
                if result:
                    key, value = result
                    try:
                        data = json.loads(value)
                        topic = data.get('topic')
                        payload = data.get('payload')
                        qos = data.get('qos', 1)
                        if topic and payload is not None:
                            # 调用 MQTT 发布
                            mqtt_client.publish(topic, payload, qos=qos)
                        else:
                            logger.warning("消息缺少 topic 或 payload")
                    except json.JSONDecodeError:
                        logger.error(f"无效 JSON: {value}")
            except Exception as e:
                logger.exception(f"Redis 监听器异常: {e}")

    def stop(self):
        self.running = False
        logger.info("Redis 监听器正在停止")
# app_mqtt/mqtt_client.py
import paho.mqtt.client as mqtt
import threading
import time
import json
from django.conf import settings
from .utils import get_logger
from . import handlers

logger = get_logger(__name__)

class MQTTClient:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.client = mqtt.Client(client_id=settings.MQTT_CLIENT_ID)
        if hasattr(settings, 'MQTT_USERNAME') and settings.MQTT_USERNAME:
            self.client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.connected = False
        self._initialized = True

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("已连接到MQTT代理")
            self.connected = True
            # 订阅主题
            topic = settings.MQTT_SUBSCRIBE_TOPICS
            client.subscribe(topic)
            logger.info(f"已订阅主题: {topic}")
        else:
            logger.error(f"连接失败，返回码 {rc}")
            self.connected = False

    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            logger.warning(f"意外断开与MQTT代理的连接，将自动重连 (rc={rc})")
        else:
            logger.info("已断开与MQTT代理的连接")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        # logger.info(f"收到消息 => {topic}: {payload}")
        handlers.handle_message(topic, payload)

    def connect(self):
        """建立连接（非阻塞）"""
        try:
            self.client.connect(settings.MQTT_HOST, settings.MQTT_PORT, settings.MQTT_KEEPALIVE)
            logger.info("正在尝试连接MQTT代理...")
        except Exception as e:
            logger.error(f"连接异常: {e}")

    def start_loop(self):
        """启动网络循环（阻塞）"""
        self.client.loop_forever()

    def publish(self, topic, payload, qos=1, retry=2):
        """
        同步发布消息，带简单重试。
        :param topic: MQTT主题
        :param payload: 消息内容（字符串或可序列化对象）
        :param qos: 服务质量等级
        :param retry: 重试次数
        :return: 是否成功
        """
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False)

        for attempt in range(retry + 1):
            if self.connected:
                result = self.client.publish(topic, payload, qos=qos)
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"发布消息成功 => {topic}: {payload}")
                    return True
                else:
                    logger.error(f"发布消息失败 (尝试 {attempt+1}/{retry+1})，错误码: {result.rc}")
            else:
                logger.warning(f"MQTT未连接，等待重试 (尝试 {attempt+1}/{retry+1})")
                time.sleep(1)  # 等待1秒后重试

        logger.error(f"发布消息最终失败: {topic}")
        return False

# 全局单例实例
mqtt_client = MQTTClient()
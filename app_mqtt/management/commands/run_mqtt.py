# app_mqtt/management/commands/run_mqtt.py
import signal
import sys
import time
from django.core.management.base import BaseCommand
from app_mqtt.mqtt_client import mqtt_client
from app_mqtt.offline_detector import OfflineDetector
from app_mqtt.utils import get_logger
from django.conf import settings

logger = get_logger(__name__)

class Command(BaseCommand):
    help = '启动 MQTT 服务（包含接收消息和离线检测）'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('启动MQTT服务…'))

        # 连接 MQTT 代理
        mqtt_client.connect()
        # 在后台线程运行网络循环
        mqtt_client.client.loop_start()

        # 启动离线检测线程
        offline_detector = OfflineDetector()
        offline_detector.start()

        self.running = True

        def signal_handler(sig, frame):
            logger.info("收到退出信号，正在关闭MQTT服务...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
        finally:
            logger.info("停止所有组件...")
            offline_detector.stop()
            mqtt_client.client.loop_stop()
            mqtt_client.client.disconnect()
            offline_detector.join(timeout=5)
            logger.info("MQTT服务已安全停止")
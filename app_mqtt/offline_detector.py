# app_mqtt/offline_detector.py
import threading
import time
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from app_device.models import Devices
from app_device_con_log.models import DeviceConLog
from .utils import get_logger
from .handlers import _device_heartbeats, _device_status, _heartbeat_lock

logger = get_logger(__name__)

class OfflineDetector(threading.Thread):
    def __init__(self):
        super().__init__()
        self.interval = getattr(settings, 'MQTT_OFFLINE_DETECT_INTERVAL', 60)
        self.timeout = getattr(settings, 'MQTT_OFFLINE_TIMEOUT', 3600)
        self.running = True
        self.daemon = True

    def run(self):
        logger.info(f"离线检测线程启动（间隔 {self.interval}s，超时 {self.timeout}s）")
        time.sleep(self.interval)  # 延迟首次检测
        while self.running:
            try:
                self.check_offline_devices()
            except Exception as e:
                logger.exception(f"离线检测异常: {e}")
            time.sleep(self.interval)

    def check_offline_devices(self):
        now = timezone.now()
        threshold = now - timedelta(seconds=self.timeout)

        # 获取心跳快照（避免长时间持锁）
        with _heartbeat_lock:
            heartbeats_snapshot = dict(_device_heartbeats)

        offline_sns = [sn for sn, hb in heartbeats_snapshot.items() if hb < threshold]

        for sn in offline_sns:
            device = Devices.objects.filter(sn_code=sn).first()
            if not device:
                continue

            # 防止重复创建离线日志
            existing_log = DeviceConLog.objects.filter(
                sn_code=device,
                online_time__isnull=True,
                offline_time__isnull=False
            ).first()
            if existing_log:
                continue

            # 创建离线日志
            try:
                log = DeviceConLog.objects.create(
                    sn_code=device,
                    offline_time=now,
                    online_time=None,
                    offline_duration="",
                    success_count=None,
                    log_time=None
                )
                # 更新数据库设备状态为离线
                device.status = '0'
                device.save(update_fields=['status'])
                # 同时更新内存状态
                with _heartbeat_lock:
                    if sn in _device_status:
                        _device_status[sn] = False
                logger.info(f"设备 {sn} 离线，创建连接日志 #{log.id}，状态设为离线")
            except Exception as e:
                logger.exception(f"创建设备 {sn} 离线日志失败: {e}")

    def stop(self):
        self.running = False
        logger.info("离线检测线程停止")
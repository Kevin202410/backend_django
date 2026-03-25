import re
import json
import time
from django.utils import timezone
import threading
from django.conf import settings
from app_mqtt.mqtt_client import mqtt_client
from app_mqtt.utils import get_logger
from app_device.models import Devices
from app_device_con_log.models import DeviceConLog
from app_attendance_record.models import AttendanceRecord
from django.core.exceptions import ObjectDoesNotExist

logger = get_logger(__name__)

# 内存缓存：设备心跳时间、首次出现时间、在线状态（线程安全）
_device_heartbeats = {}
_device_first_seen = {}
_device_status = {}
_heartbeat_lock = threading.Lock()
_response_listeners = {}
_response_lock = threading.Lock()


def handle_message(topic, payload):
    """消息路由"""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        logger.error(f"无效 JSON: {payload}")
        return

    cmd = data.get('cmd')
    if cmd == 'F1netType':
        handle_device_heartbeat(data)
    elif cmd == 'F1getTimeRecord':
        # 通知等待的线程
        with _response_lock:
            listener = _response_listeners.get(sn)
            if listener:
                listener(data)
            else:
                logger.debug(f"设备 {sn} 无等待的请求，响应忽略")
    else:
        logger.warning(f"未知命令: {cmd}")


def handle_device_heartbeat(data):
    """处理设备心跳，判断上下线并触发同步"""
    sn = data.get('sn')
    if not sn:
        logger.error("心跳消息缺少 sn")
        return

    # 获取或创建设备对象
    device = Devices.objects.filter(sn_code=sn).first()
    if not device:
        logger.error(f"设备 {sn} 不存在")
        return

    current_time = timezone.now()

    with _heartbeat_lock:
        is_first_time = sn not in _device_first_seen
        if is_first_time:
            # 首次上线：记录首次出现时间，更新数据库状态为在线
            _device_first_seen[sn] = current_time
            _device_status[sn] = True
            device.status = '1'
            device.save(update_fields=['status'])
            logger.info(f"设备 {sn} 首次上线，状态设为在线")

        was_offline = False
        offline_time = None
        if not is_first_time and sn in _device_status and not _device_status[sn]:
            # 之前是离线状态，现在恢复上线
            was_offline = True
            # 查找未完成的连接日志（有离线时间，无上线时间）
            unfinished_log = DeviceConLog.objects.filter(
                sn_code=device,
                online_time__isnull=True,
                offline_time__isnull=False
            ).first()
            if unfinished_log:
                offline_ts = unfinished_log.offline_time
                # 补全上线时间
                unfinished_log.online_time = current_time
                # 计算离线时长
                delta = current_time - offline_ts
                total_seconds = delta.total_seconds()
                days = int(total_seconds // 86400)
                hours = int((total_seconds % 86400) // 3600)
                minutes = int((total_seconds % 3600) // 60)
                parts = []
                if days > 0: parts.append(f"{days}天")
                if hours > 0: parts.append(f"{hours}小时")
                if minutes > 0: parts.append(f"{minutes}分钟")
                unfinished_log.offline_duration = "".join(parts) if parts else "瞬间恢复"
                unfinished_log.save()
                logger.info(f"设备 {sn} 重新上线，日志 #{unfinished_log.id} 时长 {unfinished_log.offline_duration}")

            # 设备状态从离线变为在线，更新数据库状态
            device.status = '1'
            device.save(update_fields=['status'])
            logger.info(f"设备 {sn} 状态从离线变为在线")

        # 更新内存心跳时间和在线状态
        _device_heartbeats[sn] = current_time
        _device_status[sn] = True

    # 如果是从离线恢复，触发同步请求（异步）
    # if was_offline and offline_ts:
    #     threading.Thread(
    #         target=send_time_record_request,
    #         args=(sn, offline_ts, current_time),
    #         daemon=True
    #     ).start()

def send_time_record_request(sn, offline_time, online_time):
    """
    从设备拉取离线期间的考勤记录，支持分页。
    :param sn: 设备序列号
    :param offline_time: 离线时间（datetime对象）
    :param online_time: 上线时间（datetime对象）
    """
    # 构造时间范围（向前延伸10分钟，确保覆盖）
    start_ts = offline_time.timestamp() - 600
    end_ts = online_time.timestamp()
    start_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_ts))
    end_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_ts))

    # 分页参数
    page = 1
    max_pages = 1000
    page_size = 100
    total_records = None
    fetched_records = 0
    max_retries = 2
    retry_delay = 2

    # 连接日志（用于更新同步结果）
    device = Devices.objects.filter(sn_code=sn).first()
    if not device:
        logger.error(f"设备 {sn} 不存在，无法同步")
        return

    # 查找本次上线的连接日志（online_time 刚补全的）
    current_log = DeviceConLog.objects.filter(
        sn_code=device,
        online_time=online_time,
        offline_time__isnull=False
    ).first()
    if not current_log:
        logger.warning(f"设备 {sn} 未找到对应的连接日志，将不记录同步结果")
        # 仍然尝试同步，但不更新日志

    # 临时监听器：用于等待设备响应
    def make_listener(event, result):
        def on_response(data):
            result['data'] = data
            event.set()
        return on_response

    # 发送请求并处理响应
    for page in range(1, max_pages + 1):
        # 构造请求
        request = {
            "cmd": "F1getTimeRecord",
            "token": "",
            "sn": sn,
            "page": page,
            "startTime": start_time_str,
            "endTime": end_time_str
        }
        topic = f"cs/{sn}/msg"
        payload = json.dumps(request, ensure_ascii=False)

        # 准备响应等待
        event = threading.Event()
        result = {}
        with _response_lock:
            _response_listeners[sn] = make_listener(event, result)

        # 发送请求（带重试）
        retries = 0
        published = False
        while retries < max_retries:
            try:
                if mqtt_client.publish(topic, payload, qos=1):
                    published = True
                    break
            except Exception as e:
                logger.error(f"设备 {sn} 第{page}页发布失败: {e}")
            retries += 1
            time.sleep(retry_delay)

        if not published:
            logger.error(f"设备 {sn} 第{page}页请求发送失败，终止同步")
            break

        # 等待响应（超时5秒）
        if not event.wait(timeout=5):
            logger.warning(f"设备 {sn} 第{page}页响应超时")
            # 清理监听器
            with _response_lock:
                _response_listeners.pop(sn, None)
            # 重试本页（最多2次）
            if page > 1:
                # 若非第一页，可能丢失数据，不再重试
                break
            else:
                # 第一页失败，尝试重发一次
                continue

        # 响应到达，处理数据
        response = result.get('data', {})
        body = response.get('body', [])
        count = response.get('count', 0)      # 总记录数
        number = response.get('number', 0)    # 本页实际返回数量

        if total_records is None:
            total_records = count
            logger.info(f"设备 {sn} 总记录数: {total_records}")

        # 保存考勤记录
        for record in body:
            # 根据实际模型字段映射
            AttendanceRecord.objects.get_or_create(
                sn_code=sn,
                record_time=record.get('time'),
                defaults={
                    'user_id': record.get('userId'),
                    'record_type': record.get('type'),
                    # 其他字段根据设备文档补充
                }
            )
        fetched_records += len(body)
        logger.info(f"设备 {sn} 第{page}页获取{number}条，累计{fetched_records}/{total_records}")

        # 终止条件
        if total_records == 0 or fetched_records >= total_records or number < page_size or len(body) == 0:
            logger.info(f"设备 {sn} 翻页结束，共{page}页")
            break

        # 稍等再发下一页，避免设备压力
        time.sleep(0.5)

    # 更新连接日志的同步结果
    if current_log:
        current_log.success_count = fetched_records
        current_log.log_time = timezone.now()
        current_log.save(update_fields=['success_count', 'log_time'])
        logger.info(f"设备 {sn} 同步完成，记录数 {fetched_records}")
    else:
        logger.info(f"设备 {sn} 同步完成，记录数 {fetched_records}，但未找到连接日志")

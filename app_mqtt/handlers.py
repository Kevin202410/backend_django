import re
import json
import time
from datetime import datetime
import redis
from async_timeout import timeout
from django.utils import timezone
import threading
from django.conf import settings
from app_mqtt.models import AuthorizationRecord
from app_mqtt.mqtt_client import mqtt_client
from app_mqtt.utils import get_logger
from app_device.models import Devices
from app_device_con_log.models import DeviceConLog
from app_attendance_record.models import AttendanceRecord
from django.core.exceptions import ObjectDoesNotExist
from app_user.models import Users

logger = get_logger(__name__)
# 内存缓存：设备心跳时间、首次出现时间、在线状态（线程安全）
_device_heartbeats = {}
_device_first_seen = {}
_device_status = {}
_heartbeat_lock = threading.Lock()
_response_listeners = {}
_response_lock = threading.Lock()


def handle_message(topic, payload):
    """消息路由：统一处理MQTT消息，核心入口"""
    try:
        # 1. 基础解析：JSON解码 + 提取核心字段
        data = json.loads(payload)
        sn = data.get('sn')
        cmd = data.get('cmd')

        # 2. 命令路由
        if cmd == 'F1netType':
            handle_device_heartbeat(data)
        elif cmd == 'F1getTimeRecord':
            with _response_lock:
                listener = _response_listeners.get(sn)
                if listener:
                    listener(data)
                    # 清理监听器，避免内存泄漏
                    _response_listeners.pop(sn, None)
                else:
                    logger.debug(f"设备 {sn} 无等待的请求，响应忽略")
        elif cmd == 'F1redactUser':
            handle_user_registration_response(data)
        elif cmd == 'F1deleteUser':
            handle_user_delete_response(data)
        elif cmd == 'F1getDevInfo':
            handle_device_info_response(data)
        else:
            logger.warning(f"未知命令: {cmd} (设备SN: {sn})")

    except json.JSONDecodeError:
        logger.error(f"无效JSON格式: {payload}")
    except Exception as e:
        # 全局异常捕获：防止单条消息崩溃MQTT线程
        logger.error(f"处理MQTT消息异常: {str(e)}", exc_info=True)

def handle_device_heartbeat(data):
    """处理设备心跳，判断上下线并触发考勤同步"""
    try:
        sn = data.get('sn')
        if not sn:
            logger.error("心跳消息缺少 sn")
            return

        # 获取或创建设备对象
        device = Devices.objects.filter(sn_code=sn).first()
        if not device:
            logger.error(f"设备 {sn} 不存在于数据库")
            return

        current_time = timezone.now()
        offline_ts = None  # 初始化离线时间，避免未定义
        with _heartbeat_lock:
            is_first_time = sn not in _device_first_seen
            was_offline = False

            # 首次上线处理
            if is_first_time:
                _device_first_seen[sn] = current_time
                _device_status[sn] = True
                # 更新设备在线状态
                device.status = '1'
                device.save(update_fields=['status'])
                logger.info(f"设备 {sn} 首次上线，状态设为在线")
                send_get_device_info(sn)

            # 离线恢复处理
            else:
                # 检查是否从离线恢复
                if sn in _device_status and not _device_status[sn]:
                    was_offline = True
                    # 查找未完成的离线日志（有离线时间，无上线时间）
                    unfinished_log = DeviceConLog.objects.filter(
                        sn_code=device,
                        online_time__isnull=True,
                        offline_time__isnull=False
                    ).first()
                    if unfinished_log:
                        offline_ts = unfinished_log.offline_time  # 赋值离线时间
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
                        logger.info(
                            f"设备 {sn} 重新上线 | 离线时长: {unfinished_log.offline_duration} | 日志ID: {unfinished_log.id}")

                    # 更新设备在线状态
                    device.status = '1'
                    device.save(update_fields=['status'])
                    logger.info(f"设备 {sn} 状态从离线变为在线")

            # 更新内存缓存
            _device_heartbeats[sn] = current_time
            _device_status[sn] = True

        # 离线恢复时触发考勤同步（异步执行，不阻塞心跳处理）
        if was_offline and offline_ts:
            threading.Thread(
                target=send_time_record_request,
                args=(sn, offline_ts, current_time),
                daemon=True
            ).start()

    except Exception as e:
        logger.error(f"处理设备心跳异常 (SN: {data.get('sn')}): {str(e)}", exc_info=True)

def handle_user_registration_response(data):
    """处理设备返回的人员注册响应，更新授权记录状态"""
    try:
        sn = data.get('sn')
        token = data.get('token')   # 用户ID
        result = data.get('result')
        if not sn or token is None or result is None:
            logger.error(f"注册响应缺少必要字段: sn={sn}, token={token}, result={result}")
            return

        device = Devices.objects.filter(sn_code=sn).first()
        if not device:
            logger.error(f"设备 {sn} 不存在，无法更新授权记录")
            return

        # token 可能是字符串形式的数字，尝试转换为整数
        try:
            user_id = int(token.split('/')[0])
        except (TypeError, ValueError):
            logger.error(f"无效的用户ID token: {token}")
            return
        user = Users.objects.filter(id=user_id).first()
        if not user:
            logger.error(f"用户 {user_id} 不存在，无法更新授权记录")
            return
        try:
            validity = datetime.fromtimestamp(int(token.split('/')[1]))
        except (TypeError, ValueError):
            validity = None

        # 查询或创建授权记录
        auth_record, created = AuthorizationRecord.objects.get_or_create(
            user=user,
            device=device,
            defaults={
                'status': result,
                'validity': validity
            }
        )

        if result is not None:
            auth_record.status = result
            auth_record.validity = validity
            auth_record.save()
            if result == 0:
                logger.info(f"授权记录更新成功：用户 {user_id} 设备 {sn} 状态 -> 已授权")
            else:
                logger.warning(f"授权记录更新失败：用户 {user_id} 设备 {sn} 状态 -> {result} ({dict(AuthorizationRecord.STATUS_CHOICES).get(result, '未知错误')})")
        else:
            logger.debug(f"用户 {user_id} 设备 {sn} 状态无需更新")

    except Exception as e:
        logger.error(f"处理授权响应异常: {str(e)}", exc_info=True)

def handle_user_delete_response(data):
    """处理设备返回的删除人员响应，将本地授权记录状态标记为 1（已禁用/已删除）"""
    try:
        sn = data.get('sn')
        token = data.get('token', '')
        result = data.get('result')

        if not sn or not token:
            logger.error(f"删除响应缺少必要字段: sn={sn}, token={token}")
            return

        if result != 0:
            logger.warning(f"设备 {sn} 删除人员失败: result={result}, errmsg={data.get('errmsg', '')}")
            return

        # 解析 token，格式如 "工号1-工号2"
        jobnumber_strs = token.split('-')
        jobnumbers = []
        for js in jobnumber_strs:
            try:
                jobnumbers.append(int(js))
            except ValueError:
                logger.warning(f"无效的工号格式: {js}")
                continue

        if not jobnumbers:
            logger.warning(f"设备 {sn} 返回的 token 中未解析出有效工号: {token}")
            return

        # 查找设备
        device = Devices.objects.filter(sn_code=sn).first()
        if not device:
            logger.error(f"设备 {sn} 不存在，无法更新授权记录")
            return

        # 批量更新授权记录状态为 1（已禁用/已删除）
        updated_count = AuthorizationRecord.objects.filter(
            device=device,
            user__id__in=jobnumbers
        ).update(status=1, update_time=timezone.now())

        if updated_count:
            logger.info(f"设备 {sn} 删除人员成功，已将 {updated_count} 条授权记录状态设为 1 (工号: {jobnumbers})")
        else:
            logger.warning(f"设备 {sn} 删除人员成功，但未找到对应的授权记录 (工号: {jobnumbers})")

    except Exception as e:
        logger.error(f"处理删除人员响应异常: {str(e)}", exc_info=True)

def handle_device_info_response(data):
    """处理设备返回的设备信息，更新数据库中的设备信息字段"""
    try:
        sn = data.get('sn')
        if not sn:
            return

        device = Devices.objects.filter(sn_code=sn).first()
        if not device:
            logger.error(f"设备 {sn} 不存在，无法更新设备信息")
            return

        # 可更新的字段列表（与设备返回的字段名一致）
        field_mapping = {
            'model': 'model',
            'version': 'version',
            'vender': 'vender',
            'mac': 'mac',
            'ipaddress': 'ipaddress',
            'userNumber': 'userNumber',
            'record': 'record',
            'face': 'face',
        }
        update_data = {}
        for dev_field, model_field in field_mapping.items():
            if dev_field in data:
                update_data[model_field] = data[dev_field]

        if update_data:
            # 使用 update 方法批量更新，避免触发模型 save 方法，同时只更新提供的字段
            Devices.objects.filter(sn_code=sn).update(**update_data)
        else:
            logger.debug(f"设备 {sn} 信息响应中无有效字段: {data}")

    except Exception as e:
        logger.error(f"处理设备信息响应异常: {str(e)}", exc_info=True)

def send_time_record_request(sn, offline_time, online_time):
    """
    异步拉取设备离线期间的考勤记录（支持分页）
    :param sn: 设备序列号
    :param offline_time: 离线时间（datetime）
    :param online_time: 上线时间（datetime）
    """
    try:
        # 1. 基础校验
        device = Devices.objects.filter(sn_code=sn).first()
        if not device:
            logger.error(f"设备 {sn} 不存在，终止考勤同步")
            return

        # 2. 时间范围转换（设备端需要字符串格式）
        start_ts = int(offline_time.timestamp())
        end_ts = int(online_time.timestamp())
        start_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_ts))
        end_time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_ts))

        # 3. 分页配置
        page = 1
        max_pages = 100  # 防止无限翻页
        page_size = 100
        total_records = 0
        fetched_records = 0
        new_records = 0  # 新增记录数（修复：初始化累加器）
        max_retries = 2
        retry_delay = 2

        # 4. 查找本次上线的连接日志（用于更新同步结果）
        current_log = DeviceConLog.objects.filter(
            sn_code=device,
            online_time=online_time,
            offline_time__isnull=False
        ).first()

        # 5. 定义响应监听器（闭包）
        def make_listener(event, result):
            def on_response(data):
                result['data'] = data
                event.set()  # 触发事件，结束等待

            return on_response

        # 6. 分页拉取考勤记录
        logger.info(f"开始同步设备 {sn} 离线考勤 | 时间范围: {start_time_str} ~ {end_time_str}")
        while page <= max_pages:
            # 构造请求体
            request_data = {
                "cmd": "F1getTimeRecord",
                "token": "",
                "sn": sn,
                "page": page,
                "startTime": start_time_str,
                "endTime": end_time_str
            }
            topic = f"cs/{sn}/msg"
            payload = json.dumps(request_data, ensure_ascii=False)

            # 准备响应等待
            event = threading.Event()
            result = {}
            with _response_lock:
                _response_listeners[sn] = make_listener(event, result)

            # 发送请求（带重试）
            published = False
            retries = 0
            while retries < max_retries:
                try:
                    rc, mid = mqtt_client.publish(topic, payload, qos=1)
                    if rc == 0:
                        published = True
                        break
                    logger.warning(f"设备 {sn} 第{page}页发布失败 (rc={rc})，重试{retries + 1}/{max_retries}")
                except Exception as e:
                    logger.error(f"设备 {sn} 第{page}页发布异常: {str(e)}")
                retries += 1
                time.sleep(retry_delay)

            if not published:
                logger.error(f"设备 {sn} 第{page}页请求发送失败，终止同步")
                break

            # 等待设备响应（超时5秒）
            if not event.wait(timeout=5):
                logger.warning(f"设备 {sn} 第{page}页响应超时")
                # 清理监听器
                with _response_lock:
                    _response_listeners.pop(sn, None)
                # 第一页超时重试一次，其他页直接终止
                if page == 1:
                    continue
                else:
                    break

            # 处理设备响应
            response = result.get('data', {})
            body = response.get('body', [])
            count = response.get('count', 0)
            number = response.get('number', 0)

            # 初始化总记录数
            if total_records == 0:
                total_records = count
                logger.info(f"设备 {sn} 待同步考勤总数: {total_records}")

            # 保存考勤记录
            page_new = 0  # 本页新增记录数
            for record in body:
                user_id = record.get('userId')
                time_ts = record.get('time')
                if not user_id or not time_ts:
                    logger.warning(f"设备 {sn} 第{page}页记录缺少字段: {record}")
                    continue

                # 时间戳转换（兼容秒级时间戳）
                try:
                    record_datetime = datetime.fromtimestamp(int(time_ts))
                    # 转换为Django时区时间
                    record_datetime = timezone.make_aware(record_datetime)
                except Exception as e:
                    logger.error(f"设备 {sn} 时间戳转换失败: {time_ts} | {str(e)}")
                    continue

                # 匹配用户
                user = Users.objects.filter(id=user_id).first()
                if not user:
                    logger.warning(f"设备 {sn} 记录中用户 {user_id} 不存在")
                    continue

                # 去重保存
                try:
                    obj, created = AttendanceRecord.objects.get_or_create(
                        user=user,
                        device=device,
                        time_stamp=record_datetime,
                        defaults={'command': 'F1getTimeRecord'}
                    )
                    if created:
                        page_new += 1
                        new_records += 1  # 累计新增记录数（修复：正确累加）
                except Exception as e:
                    logger.error(f"保存考勤记录失败: {str(e)}", exc_info=True)

            # 统计本页数据
            fetched_records += number
            logger.info(
                f"设备 {sn} 第{page}页 | 获取{number}条 | 新增{page_new}条 | 累计{fetched_records}/{total_records}")

            # 终止翻页条件
            if fetched_records >= total_records or number < page_size or total_records == 0:
                break

            page += 1
            time.sleep(0.5)  # 避免高频请求压垮设备

        # 7. 更新连接日志的同步结果
        if current_log:
            current_log.success_count = new_records
            current_log.log_time = timezone.now()
            current_log.save(update_fields=['success_count', 'log_time'])
            logger.info(f"设备 {sn} 考勤同步完成 | 新增记录: {new_records} | 日志ID: {current_log.id}")
        else:
            logger.info(f"设备 {sn} 考勤同步完成 | 新增记录: {new_records} (未找到对应连接日志)")

    except Exception as e:
        logger.error(f"同步设备 {sn} 考勤记录异常: {str(e)}", exc_info=True)

def send_get_device_info(sn):
    """向指定设备发送获取设备信息命令（通过 Redis 队列）"""
    try:
        message = {
            "cmd": "F1getDevInfo",
            "token": "",
            "sn": sn
        }
        topic = f"cs/{sn}/msg"
        payload = json.dumps(message, ensure_ascii=False)
        redis_msg = {
            "topic": topic,
            "payload": payload,
            "qos": 1
        }
        r = redis.from_url(
            settings.REDIS_URL,
            db=settings.MQTT_REDIS_DB,
            decode_responses=True
        )
        r.rpush(settings.MQTT_REDIS_LIST_KEY, json.dumps(redis_msg))
    except Exception as e:
        logger.error(f"发送获取设备信息命令失败: {e}")
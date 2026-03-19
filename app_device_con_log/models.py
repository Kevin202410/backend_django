from django.db import models

# Create your models here.
from app_device.models import Devices
from utils.models import BaseModel, table_prefix

# Create your models here.

class DeviceConLog(BaseModel):
    sn_code = models.ForeignKey(
        Devices,
        to_field='sn_code',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="关联设备",
        help_text="关联的门禁设备"
    )
    offline_time = models.DateTimeField(
        null=True, blank=True, verbose_name="离线时间", help_text='离线时间'
    )  # 离线的时间
    online_time = models.DateTimeField(
        null=True, blank=True, verbose_name="上线时间", help_text='上线时间'
    )
    offline_duration = models.CharField(
        max_length=40, null=True, blank=True, default="", verbose_name="离线时长", help_text='离线时长'
    )
    success_count = models.IntegerField(
        null=True, blank=True, verbose_name="离线期间记录数", help_text='离线期间记录数'
    )
    log_time = models.DateTimeField(
        null=True, blank=True, verbose_name="同步完成时间", help_text='同步完成时间'
    )


    class Meta:
        verbose_name = '设备连接日志'
        verbose_name_plural = verbose_name
        db_table = table_prefix + 'device_con_log'
        ordering = ("-offline_time",)

    def save(self, *args, **kwargs):
        """
        重写save方法：
        1. 设备上线时自动计算离线时长
        2. 格式化时长为：天 小时 分钟
        3. 自动刷新关联设备的在线/离线状态
        """
        # 核心逻辑：仅当 离线时间 和 上线时间 都存在时，计算时长
        if self.offline_time and self.online_time:
            # 计算时间差（兼容时区）
            delta = self.online_time - self.offline_time
            total_seconds = delta.total_seconds()

            # 转换为天、小时、分钟
            days = int(total_seconds // 86400)
            hours = int((total_seconds % 86400) // 3600)
            minutes = int((total_seconds % 3600) // 60)

            # 拼接人性化格式（自动省略0值）
            duration_list = []
            if days > 0:
                duration_list.append(f"{days}天")
            if hours > 0:
                duration_list.append(f"{hours}小时")
            if minutes > 0:
                duration_list.append(f"{minutes}分钟")

            # 无时长时显示"瞬间恢复"
            self.offline_duration = "".join(duration_list) if duration_list else "瞬间恢复"


        # 先执行日志的默认保存逻辑
        super().save(*args, **kwargs)
        # ===================== 修复核心逻辑 =====================
        # 直接获取外键关联的设备（不需要再次查询！）
        device = self.sn_code

        # 如果设备为空，直接跳过，避免报错
        if not device:
            print(f"日志未关联设备，跳过状态更新 | 日志ID: {self.id}")
            return

        # 3. 更新设备状态
        try:
            if self.online_time:
                device.status = '1'  # 在线
            elif self.offline_time and not self.online_time:
                device.status = '0'  # 离线

            # 仅更新状态字段，提升性能
            device.save(update_fields=['status'])
            print(
                f"设备【{device.device_name}({device.sn_code})】状态已更新：{'在线' if device.status == '1' else '离线'}")

        except Exception as e:
            print(f"更新设备状态失败 | SN: {device.sn_code} | 错误: {str(e)}")
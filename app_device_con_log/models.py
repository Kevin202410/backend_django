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
        ordering = ("create_datetime",)

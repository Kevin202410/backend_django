from django.db import models

# Create your models here.
from app_dept.models import Dept
from app_user.models import Users
from app_device.models import Devices
from utils.models import BaseModel, table_prefix

# Create your models here.
class AttendanceRecord(BaseModel):
    user = models.ForeignKey(
        Users,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="关联用户",
        help_text="关联用户列表ID",
        related_name="attendance_records"  # 反向关联名：用户.attendance_records
    )
    device = models.ForeignKey(
        Devices,
        to_field='sn_code',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="关联设备",
        help_text="关联的门禁设备",
        related_name="created_attendance_records"
    )
    time_stamp = models.DateTimeField(
        verbose_name='考勤时间',
        help_text="考勤时间"
    )
    command = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name='命令类型',
        help_text="命令类型"
    )
    img_address = models.FileField(
        upload_to='attendance/',
        null=True,
        blank=True,
        verbose_name='考勤凭证',
        help_text="考勤凭证"
    )
    status = models.SmallIntegerField(
        verbose_name='状态码',
        default=0,
        help_text="状态码0未同步1已同步2不同步"
    )
    class Meta:
        db_table = table_prefix + "attendance_record"
        verbose_name = "考勤记录表"
        verbose_name_plural = verbose_name
        ordering = ("-time_stamp",)
        unique_together = (('user', 'device', 'time_stamp'),)
        indexes = [
            # 新增索引提升查询性能
            models.Index(fields=["time_stamp"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["device", "time_stamp"]),
        ]

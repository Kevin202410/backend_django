from django.db import models

# Create your models here.
from app_dept.models import Dept
from utils.models import BaseModel, table_prefix

# Create your models here.
class Devices(BaseModel):
    """
    设备管理模型
    风格与Users模型完全保持一致
    """
    # 设备状态 0=离线 1=在线
    STATUS_CHOICES = (
        ('0', "离线"),
        ('1', "在线"),
    )
    device_name = models.CharField(
        max_length=20, verbose_name="门禁名称", help_text="门禁名称"
    )
    device_address = models.CharField(
        max_length=40, verbose_name='门禁位置', help_text='门禁位置'
    )
    sn_code = models.CharField(
        max_length=20,
        unique=True,  # 关键：添加唯一约束
        verbose_name="序列号", help_text="设备SN序列号"
    )
    status = models.CharField(
        max_length=1, choices=STATUS_CHOICES, default='0',
        verbose_name="设备状态", help_text="0=离线 1=在线"
    )
    sort = models.IntegerField(
        default=1, verbose_name="显示排序", help_text="显示排序"
    )
    # 关联部门
    dept = models.ForeignKey(
        to=Dept, on_delete=models.SET_NULL,
        null=True, blank=True, db_constraint=False,
        verbose_name="所属部门", help_text="使用部门"
    )
    remark = models.CharField(
        max_length=255, null=True, blank=True,
        verbose_name="备注", help_text="备注信息"
    )
    is_delete = models.BooleanField(
        default=False, verbose_name="逻辑删除", help_text="是否逻辑删除"
    )

    class Meta:
        db_table = table_prefix + "devices"
        verbose_name = "门禁设备列表"
        verbose_name_plural = verbose_name
        ordering = ("sort",)

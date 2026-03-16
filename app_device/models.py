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

    def save(self, *args, **kwargs):
        """
        重写save方法：自动根据最新连接日志更新设备状态
        规则：
        1. 无连接日志 → 状态=离线(0)
        2. 最后一次为上线 → 状态=在线(1)
        3. 最后一次为离线/未上线 → 状态=离线(0)
        """
        # 🔥 修复核心：只有已保存的对象（有主键），才查询关联日志
        if self.pk:
            # 获取当前设备最新的一条连接日志（按离线时间倒序）
            latest_log = self.conn_log.order_by('-offline_time').first()
            if latest_log:
                # 判断：有上线时间 且 上线时间晚于离线时间 → 在线
                if latest_log.online_time and (
                        not latest_log.offline_time or latest_log.online_time > latest_log.offline_time):
                    self.status = '1'
                else:
                    self.status = '0'
            else:
                # 无日志默认离线
                self.status = '0'
        # 执行父类保存逻辑
        super().save(*args, **kwargs)

    class Meta:
        db_table = table_prefix + "devices"
        verbose_name = "门禁设备列表"
        verbose_name_plural = verbose_name
        ordering = ("sort",)

class DeviceConLog(BaseModel):
    sn_code = models.ForeignKey(
        to='Devices',
        to_field='sn_code',
        on_delete=models.CASCADE,
        verbose_name='门禁编号',
        help_text='关联设备表门禁编号'
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


        # 执行默认保存逻辑
        super().save(*args, **kwargs)

        # 🔥 修复：仅当设备已存在（有主键）时，才刷新状态
        if self.device_code and self.device_code.pk:
            self.device_code.save()
    class Meta:
        verbose_name = '设备连接日志'
        verbose_name_plural = verbose_name
        db_table = table_prefix + 'device_con_log'
        ordering = ("-offline_time",)
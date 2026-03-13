import secrets
import threading
import time
from django.db import models
from application import settings

table_prefix = "sys_"  # 数据库表名前缀

class SnowflakeIDField(models.BigIntegerField):
    """
    8位雪花ID字段（仅新增时生成，更新保留原ID）
    结构：6位秒级时间戳后6位 + 2位序列号（0-99），总8位数字
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 初始化序列号和上一次时间戳（线程安全）
        self._seq = 0
        self._last_timestamp = -1
        self._lock = threading.Lock()  # 线程锁，防止并发序列号重复

    def _get_timestamp(self):
        """获取秒级时间戳的后6位（00000-99999）"""
        # 1. 获取当前秒级时间戳
        current_ts = int(time.time())
        # 2. 取后6位（缩小到6位范围）
        ts_5bit = current_ts % 100000000
        return ts_5bit

    def generate_id(self):
        """生成8位唯一ID"""
        with self._lock:  # 加锁保证线程安全
            current_ts = self._get_timestamp()

            # 处理时间回拨（若当前时间戳 < 上一次，强制等待1秒）
            if current_ts < self._last_timestamp:
                time.sleep(1)
                current_ts = self._get_timestamp()

            # 同一时间戳内，序列号自增（0-7循环）
            if current_ts == self._last_timestamp:
                self._seq = (self._seq + 1) % 99  # 3位序列号，最大7
            else:
                self._seq = 0  # 新时间戳，序列号重置为0

            # 更新上一次时间戳
            self._last_timestamp = current_ts

            # 拼接8位ID：5位时间戳 + 3位序列号（补零保证3位）
            # 例：时间戳=12345，序列号=3 → 12345003（8位）
            eight_bit_id = current_ts * 100 + self._seq

            # 兜底：确保ID是8位（防止极端情况时间戳不足5位，补前导零转整数）
            if eight_bit_id < 1000000000:
                eight_bit_id += 1000000000  # 保证8位，避免0开头

            return eight_bit_id

    def pre_save(self, model_instance, add):
        """仅新增时生成8位雪花ID，更新时保留原ID"""
        if add:
            eight_bit_id = self.generate_id()
            setattr(model_instance, self.attname, eight_bit_id)
            return eight_bit_id
        return getattr(model_instance, self.attname)

class BaseModel(models.Model):
    """
    基本模型,可直接继承使用，一般不需要使用审计字段的模型可以使用
    覆盖字段时, 字段名称请勿修改
    """
    # id = models.BigAutoField(primary_key=True, default=generate_id, help_text="Id", verbose_name="Id")
    id = SnowflakeIDField(primary_key=True)
    creator = models.ForeignKey(to=settings.AUTH_USER_MODEL, related_query_name='creator_query', null=True,
                                verbose_name='创建人', help_text="创建人", on_delete=models.SET_NULL,
                                db_constraint=False)
    modifier = models.CharField(max_length=255, null=True, blank=True, help_text="修改人", verbose_name="修改人")
    update_datetime = models.DateTimeField(auto_now=True, null=True, blank=True, verbose_name='更新时间')
    create_datetime = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name='创建时间')

    class Meta:
        abstract = True  # 表示该类是一个抽象类，只用来继承，不参与迁移操作
        verbose_name = '基本模型'
        verbose_name_plural = verbose_name

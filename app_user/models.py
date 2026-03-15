import hashlib
from django.contrib.auth.models import AbstractUser
from django.db import models
from app_post.models import Post
from app_role.models import Role
from app_dept.models import Dept
from utils.models import BaseModel, table_prefix

class Users(BaseModel, AbstractUser):
    IS_STATUS = (
        ('0', "正常"),
        ('1', "停用"),
    )
    GENDER_CHOICES = (
        ('0', "男"),
        ('1', "女"),
        ('2', "未知"),
    )

    # 核心业务字段
    id_card = models.CharField(
        max_length=18,
        unique=True,
        verbose_name="身份证号",
        help_text="18位居民身份证号，末尾X自动转为大写"
    )
    status = models.CharField(
        max_length=1,
        choices=IS_STATUS,
        default='0',
        verbose_name="用户状态",
        help_text="0正常 1停用"
    )
    username = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        verbose_name="用户账号"
    )
    nickname = models.CharField(
        max_length=150,
        verbose_name="用户姓名"
    )
    employee_no = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        verbose_name="用户工号"
    )
    email = models.EmailField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="邮箱"
    )
    phone = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name="手机号"
    )
    avatar = models.FileField(
        upload_to='avatars/',
        null=True,
        blank=True,
        verbose_name='头像'
    )
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        default='2',
        verbose_name="性别"
    )

    # 关联字段
    post = models.ManyToManyField(
        to=Post,
        blank=True,
        verbose_name="关联岗位",
        db_constraint=False
    )
    role = models.ManyToManyField(
        to=Role,
        blank=True,
        verbose_name="关联角色",
        db_constraint=False
    )
    dept = models.ForeignKey(
        to=Dept,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="所属部门",
        db_constraint=False
    )

    # 系统字段
    last_token = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="最后登录Token"
    )
    is_delete = models.BooleanField(
        default=False,
        verbose_name="逻辑删除"
    )
    remark = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        verbose_name="备注"
    )

    # 移除AbstractUser冗余字段
    first_name = None
    last_name = None
    groups = None
    user_permissions = None

    def _get_gender_from_id_card(self):
        """从身份证号提取性别：第17位 奇数=男(0) 偶数=女(1)"""
        if not self.id_card or len(self.id_card) != 18:
            return '2'
        try:
            gender_digit = int(self.id_card[16])
            return '0' if gender_digit % 2 == 1 else '1'
        except (ValueError, IndexError):
            return '2'

    def save(self, *args, **kwargs):
        """重写save：自动格式化身份证号+自动识别性别"""
        if self.id_card:
            # 自动转大写（适配末尾X）
            self.id_card = self.id_card.strip().upper()
            # 自动识别性别
            self.gender = self._get_gender_from_id_card()
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        """重写密码加密：MD5加密（保持原逻辑）"""
        md5_pwd = hashlib.md5(raw_password.encode("UTF-8")).hexdigest()
        super().set_password(md5_pwd)

    class Meta:
        db_table = table_prefix + "users"
        verbose_name = "用户表"
        verbose_name_plural = verbose_name
        ordering = ("-create_datetime",)
import hashlib
from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
from app_post.models import Post
from app_role.models import Role
from app_dept.models import Dept
from utils.models import BaseModel, table_prefix


class Users(BaseModel, AbstractUser):
    IS_STATUS = (
        ('0', "正常"),
        ('1', "停用"),
    )
    id_card = models.CharField(max_length=18, unique=True, verbose_name="身份证号", help_text="18位居民身份证号，末尾X自动转为大写")
    status = models.CharField(max_length=1, choices=IS_STATUS, default='0', verbose_name="用户状态（0正常 1停用）", help_text="用户状态（0正常 1停用）")
    username = models.CharField(max_length=150, unique=True, db_index=True, verbose_name="用户账号", help_text="用户账号")
    nickname = models.CharField(max_length=150, unique=False, verbose_name="用户姓名", help_text="用户姓名")
    employee_no = models.CharField(max_length=150, unique=True, db_index=True, null=True, blank=True, verbose_name="用户工号", help_text="工号")
    email = models.EmailField(max_length=255, verbose_name="邮箱", null=True, blank=True, help_text="邮箱")
    phone = models.CharField(max_length=255, verbose_name="手机号", null=True, blank=True, help_text="手机号")
    avatar = models.CharField(max_length=255, verbose_name="头像", null=True, blank=True, help_text="头像")
    GENDER_CHOICES = (
        ('0', "男"),
        ('1', "女"),
        ('2', "未知"),
    )
    gender = models.CharField(
        max_length=1, choices=GENDER_CHOICES, verbose_name="性别", null=True, blank=True, help_text="性别"
    )
    post = models.ManyToManyField(to=Post, blank=True, verbose_name="关联岗位", db_constraint=False,
                                  help_text="关联岗位")
    role = models.ManyToManyField(to=Role, blank=True, verbose_name="关联角色", db_constraint=False,
                                  help_text="关联角色")
    dept = models.ForeignKey(
        to=Dept,
        verbose_name="所属部门",
        on_delete=models.PROTECT,
        db_constraint=False,
        null=True,
        blank=True,
        help_text="关联部门",
    )
    last_token = models.CharField(max_length=255, null=True, blank=True, verbose_name="最后一次登录Token",
                                  help_text="最后一次登录Token")
    is_delete = models.BooleanField(default=False, verbose_name="是否逻辑删除", help_text="是否逻辑删除")
    remark = models.CharField(max_length=128, verbose_name="备注", help_text="备注", null=True, blank=True)


    # 删除继承的类中不需要的字段
    first_name = None
    last_name = None
    groups = None
    user_permissions = None

    # 新增：身份证号识别性别方法
    def _get_gender_from_id_card(self):
        """从身份证号提取性别：第17位，奇数=男(0)，偶数=女(1)"""
        if not self.id_card or len(self.id_card) != 18:
            return None
        try:
            # 第17位数字（索引16）
            gender_digit = int(self.id_card[16])
            return '0' if gender_digit % 2 == 1 else '1'
        except (IndexError, ValueError):
            return None

    # 重写save方法，自动填充性别
    def save(self, *args, **kwargs):
        # 如果有身份证号，自动识别性别
        if self.id_card:
            self.gender = self._get_gender_from_id_card() or self.gender
        # 无身份证号时，性别置为未知（可选）
        else:
            self.gender = '2'
        super().save(*args, **kwargs)


    def set_password(self, raw_password):
        super().set_password(hashlib.md5(raw_password.encode(encoding="UTF-8")).hexdigest())

    class Meta:
        db_table = table_prefix + "users"
        verbose_name = "用户表"
        verbose_name_plural = verbose_name
        ordering = ("-create_datetime",)
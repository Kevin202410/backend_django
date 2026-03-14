import re, os
from import_export.fields import Field
from import_export import resources
from import_export.widgets import ManyToManyWidget, ForeignKeyWidget
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from app_post.models import Post
from app_role.models import Role
from app_dept.models import Dept
from app_user.models import Users
from utils.common import REGEX_MOBILE, renameuploadimg, get_full_image_url, rewrite_image_url
from utils.serializers import CustomModelSerializer
from utils.validator import CustomUniqueValidator, CustomValidationError
from utils.id_card_utlis import validate_id_card

class UserSerializer(CustomModelSerializer):
    """
    用户-序列化器
    """
    dept_name = serializers.CharField(source='dept.dept_name', read_only=True)

    class Meta:
        model = Users
        read_only_fields = ["id"]
        exclude = ["password"]


class UserCreateSerializer(CustomModelSerializer):
    """
    用户信息修改/更新-序列化器
    """
    password = serializers.CharField(required=False, default=make_password("123456"))
    username = serializers.CharField(
        max_length=50,
        validators=[CustomUniqueValidator(queryset=Users.objects.all(), message="账号必须唯一")]
    )
    nickname = serializers.CharField(
        max_length=50,
    )
    id_card = serializers.CharField(
        max_length=18,
        validators=[CustomUniqueValidator(queryset=Users.objects.all(), message="身份证号必须唯一")]
    )
    phone = serializers.CharField(
        required=False,  # 非必填
        allow_blank=True,  # 允许空字符串
        allow_null=True,  # 允许null
        validators=[CustomUniqueValidator(queryset=Users.objects.all(), message="手机号必须唯一")],
    )


    def validate_phone(self, value):
        # 空值直接返回，不校验格式
        if not value:
            return value
        # 非空值才校验格式
        if not re.match(REGEX_MOBILE, value):
            raise CustomValidationError('请输入一个有效的手机号码')
        return value

    def create(self, validated_data):
        if 'password' in validated_data.keys():
            if validated_data['password']:
                validated_data['password'] = make_password(validated_data['password'])

        return super().create(validated_data)

    def validate_id_card(self, value):
        """自定义身份证号校验"""
        is_valid, msg = validate_id_card(value)
        if not is_valid:
            raise serializers.ValidationError(msg)
        return value

    class Meta:
        model = Users
        fields = "__all__"
        read_only_fields = ["id"]


class UserResource(resources.ModelResource):
    id = Field(attribute='id', column_name=Users.id.field.verbose_name)
    status = Field(attribute='status', column_name=Users.status.field.verbose_name)
    username = Field(attribute='username', column_name=Users.username.field.verbose_name)
    nickname = Field(attribute='nickname', column_name=Users.nickname.field.verbose_name)
    id_card = Field(attribute='id_card', column_name=Users.id_card.field.verbose_name)
    employee_no = Field(attribute='employee_no', column_name=Users.employee_no.field.verbose_name)
    email = Field(attribute='email', column_name=Users.email.field.verbose_name)
    phone = Field(attribute='phone', column_name=Users.phone.field.verbose_name)
    gender = Field(attribute='gender', column_name=Users.gender.field.verbose_name)
    post = Field(
        column_name='关联岗位',
        attribute='post',
        widget=ManyToManyWidget(Post, field='post_name')
    )
    role = Field(
        column_name='关联角色',
        attribute='role',
        widget=ManyToManyWidget(Role, field='role_name')
    )
    dept = Field(
        column_name='所属部门',
        attribute='dept',
        widget=ForeignKeyWidget(Dept, field='dept_name')
    )
    remark = Field(attribute='remark', column_name=Users.remark.field.verbose_name)
    update_datetime = Field(attribute='update_datetime', column_name=Users.update_datetime.field.verbose_name)
    create_datetime = Field(attribute='create_datetime', column_name=Users.create_datetime.field.verbose_name)

    class Meta:
        model = Users
        fields = ('id', 'status', 'username', 'nickname', 'employee_no', 'email', 'phone', 'gender', 'post', 'role', 'dept', 'remark',
                  'id_card', 'update_datetime', 'create_datetime')
        export_order = fields

class UserAvatarSerializer(serializers.ModelSerializer):
    """用户头像序列化器（处理上传/读取）"""
    # 序列化时返回完整的头像URL（跨域可访问）
    avatar_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Users
        fields = ['id', 'avatar', 'avatar_url']
        extra_kwargs = {
            'avatar': {'write_only': True}  # 头像文件仅用于上传，返回时用avatar_url
        }

    def get_avatar_url(self, obj):
        """
        整合common工具函数，返回跨域可访问的完整头像URL
        :param obj: User实例
        :return: 完整URL（如https://xxx.com/media/avatars/20240520102030_123.png）
        """
        if not obj.avatar:
            return None
        # 1. 获取request对象（用于拼接域名）
        request = self.context.get('request')
        # 2. 先重写URL（移除旧环境域名，保留相对路径）
        relative_url = rewrite_image_url(request, obj.avatar.url)
        # 3. 补全完整域名（支持跨域访问）
        full_url = get_full_image_url(request, relative_url)
        return full_url

    def validate_avatar(self, value):
        """验证头像文件格式/大小"""
        # 允许的文件格式
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError("仅支持jpg/jpeg/png/gif格式的头像文件")
        # 限制文件大小（5MB）
        max_size = 5 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError("头像文件大小不能超过5MB")
        # 调用common的重命名函数，自定义头像文件名
        value.name = renameuploadimg(value.name)
        return value
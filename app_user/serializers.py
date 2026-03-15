import re
import os
from django.contrib.auth.hashers import make_password
from rest_framework import serializers
from import_export import resources
from import_export.fields import Field
from import_export.widgets import ManyToManyWidget, ForeignKeyWidget
from app_post.models import Post
from app_role.models import Role
from app_dept.models import Dept
from app_user.models import Users
from utils.common import REGEX_MOBILE, renameuploadimg, get_full_image_url, rewrite_image_url
from utils.serializers import CustomModelSerializer
from utils.validator import CustomUniqueValidator, CustomValidationError
from utils.id_card_utlis import validate_id_card

class UserSerializer(CustomModelSerializer):
    """用户-基础序列化器"""
    dept_name = serializers.CharField(source='dept.dept_name', read_only=True)

    class Meta:
        model = Users
        read_only_fields = ["id"]
        exclude = ["password"]

class UserCreateSerializer(CustomModelSerializer):
    """用户创建/更新序列化器"""
    password = serializers.CharField(required=False, default=make_password("123456"))

    class Meta:
        model = Users
        fields = "__all__"
        read_only_fields = ["id"]
        extra_kwargs = {
            "username": {
                "validators": [CustomUniqueValidator(queryset=Users.objects.all(), message="账号必须唯一")]
            },
            "id_card": {
                "validators": [CustomUniqueValidator(queryset=Users.objects.all(), message="身份证号必须唯一")]
            },
            "phone": {
                "validators": [CustomUniqueValidator(queryset=Users.objects.all(), message="手机号必须唯一")],
                "required": False,
                "allow_blank": True,
                "allow_null": True
            }
        }

    def validate_phone(self, value):
        """手机号格式校验（空值跳过）"""
        if value and not REGEX_MOBILE.match(value):
            raise CustomValidationError('请输入有效的手机号码')
        return value

    def validate_id_card(self, value):
        """身份证号合法性校验"""
        is_valid, msg = validate_id_card(value)
        if not is_valid:
            raise serializers.ValidationError(msg)
        return value

    def create(self, validated_data):
        """创建用户时加密密码"""
        if validated_data.get('password'):
            validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

class UserResource(resources.ModelResource):
    """用户导入导出资源"""
    id = Field(attribute='id', column_name=Users.id.field.verbose_name)
    status = Field(attribute='status', column_name=Users.status.field.verbose_name)
    username = Field(attribute='username', column_name=Users.username.field.verbose_name)
    nickname = Field(attribute='nickname', column_name=Users.nickname.field.verbose_name)
    id_card = Field(attribute='id_card', column_name=Users.id_card.field.verbose_name)
    employee_no = Field(attribute='employee_no', column_name=Users.employee_no.field.verbose_name)
    email = Field(attribute='email', column_name=Users.email.field.verbose_name)
    phone = Field(attribute='phone', column_name=Users.phone.field.verbose_name)
    gender = Field(attribute='gender', column_name=Users.gender.field.verbose_name)
    post = Field(column_name='关联岗位', attribute='post', widget=ManyToManyWidget(Post, 'post_name'))
    role = Field(column_name='关联角色', attribute='role', widget=ManyToManyWidget(Role, 'role_name'))
    dept = Field(column_name='所属部门', attribute='dept', widget=ForeignKeyWidget(Dept, 'dept_name'))
    remark = Field(attribute='remark', column_name=Users.remark.field.verbose_name)
    update_datetime = Field(attribute='update_datetime', column_name=Users.update_datetime.field.verbose_name)
    create_datetime = Field(attribute='create_datetime', column_name=Users.create_datetime.field.verbose_name)

    class Meta:
        model = Users
        fields = ('id', 'status', 'username', 'nickname', 'employee_no', 'email', 'phone', 'gender',
                  'post', 'role', 'dept', 'remark', 'id_card', 'update_datetime', 'create_datetime')
        export_order = fields

class UserAvatarSerializer(serializers.ModelSerializer):
    """用户头像序列化器"""
    avatar_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Users
        fields = ['id', 'avatar', 'avatar_url']
        extra_kwargs = {
            'avatar': {'write_only': True, 'required': True},  # 上传时必须提供
        }

    def get_avatar_url(self, obj):
        """生成跨域可访问的完整头像URL"""
        if not obj.avatar:
            return None
        request = self.context.get('request')
        relative_url = rewrite_image_url(request, obj.avatar.url)
        return get_full_image_url(request, relative_url)

    def validate_avatar(self, value):
        """头像文件校验"""
        allowed_ext = ['.jpg', '.jpeg', '.png', '.gif']
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_ext:
            raise serializers.ValidationError("仅支持jpg/jpeg/png/gif格式")
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("头像大小不能超过5MB")
        # 复用公共函数重命名
        value.name = renameuploadimg(value.name)
        return value
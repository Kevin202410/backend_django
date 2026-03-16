from rest_framework import serializers
from import_export import resources
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget
from app_dept.models import Dept
from app_device.models import Devices, DeviceConLog
from utils.serializers import CustomModelSerializer
from utils.validator import CustomUniqueValidator

# =====================================================
# 设备基础序列化器
# =====================================================
class DeviceSerializer(CustomModelSerializer):
    """
    设备管理-序列化器
    """
    # 展示字段
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    dept_name = serializers.CharField(source='dept.dept_name', read_only=True)

    class Meta:
        model = Devices
        fields = "__all__"
        read_only_fields = ["id"]



# =====================================================
# 设备创建/更新序列化器
# =====================================================
class DeviceCreateSerializer(CustomModelSerializer):
    """
    设备管理-创建/更新序列化器
    """
    sn_code = serializers.CharField(
        validators=[CustomUniqueValidator(queryset=Devices.objects.all(), message="门禁序列号已存在")]
    )

    class Meta:
        model = Devices
        fields = "__all__"
        read_only_fields = ["id"]


# =====================================================
# 设备连接日志序列化器
# =====================================================
class DeviceConLogSerializer(CustomModelSerializer):
    """
    设备连接日志-序列化器
    """
    device_name = serializers.CharField(source='device_code.device_name', read_only=True)
    device_address = serializers.CharField(source='device_code.device_address', read_only=True)

    class Meta:
        model = DeviceConLog
        fields = "__all__"
        read_only_fields = ["id"]


# =====================================================
# 设备导入导出资源
# =====================================================
class DeviceResource(resources.ModelResource):
    """
    设备管理-导入导出配置
    """
    dept = Field(
        attribute='dept',
        widget=ForeignKeyWidget(Dept, 'dept_name'),
        column_name='所属部门'
    )
    status = Field(attribute='status', column_name='设备状态')

    class Meta:
        model = Devices
        fields = (
            'id', 'device_code', 'device_name', 'device_address',
            'sn_code', 'status', 'dept', 'sort', 'remark'
        )
        export_order = fields
from rest_framework import serializers
from import_export import resources
from import_export.fields import Field
from import_export.widgets import ForeignKeyWidget
from app_dept.models import Dept
from app_device_con_log.models import DeviceConLog
from utils.serializers import CustomModelSerializer
from utils.validator import CustomUniqueValidator

# =====================================================
# 设备连接日志序列化器
# =====================================================
class DeviceConLogSerializer(CustomModelSerializer):
    """
    设备连接日志-序列化器
    """
    device_name = serializers.CharField(source='sn_code.device_name', read_only=True, allow_null=True)
    device_address = serializers.CharField(source='sn_code.device_address', read_only=True, allow_null=True)

    class Meta:
        model = DeviceConLog
        fields = "__all__"
        read_only_fields = ["id"]
        ordering = ["create_datetime"]

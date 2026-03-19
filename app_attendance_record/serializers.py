from rest_framework import serializers
from app_attendance_record.models import AttendanceRecord
from utils.serializers import CustomModelSerializer
from import_export import resources


class AttendanceRecordSerializer(CustomModelSerializer):
    """用户-基础序列化器"""
    username = serializers.CharField(source='user.username', read_only=True, label="姓名")
    device_name = serializers.CharField(source='device.device_name', read_only=True, label="设备名称")
    device_address = serializers.CharField(source='device.device_address', read_only=True, label="设备地址")
    device_sn_cond = serializers.CharField(source='device.sn_cond', read_only=True, label="设备SN")
    dept_name = serializers.CharField(source='user.dept.dept_name', read_only=True, label="所属部门")

    class Meta:
        model = AttendanceRecord
        fields = "__all__"
        read_only_fields = ["id"]

class AttendanceRecordCreateSerializer(CustomModelSerializer):
    """考勤记录-创建序列化器（可选：单独拆分创建逻辑）"""
    class Meta:
        model = AttendanceRecord
        fields = ["user", "device", "time_stamp", "command", "img_address", "status"]
        read_only_fields = ["id"]

class AttendanceRecordResource(resources.ModelResource):
    class Meta:
        model = AttendanceRecord
        fields = (
            'id',
            'user__username',
            'device__device_name',
            'device__device_address',
            'time_stamp',
            'img_address'
        )
        export_order = fields
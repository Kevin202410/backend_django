from rest_framework import serializers
from app_attendance_record.models import AttendanceRecord
from utils.serializers import CustomModelSerializer
from import_export import resources
from datetime import datetime


class AttendanceRecordSerializer(CustomModelSerializer):
    """考勤记录-基础序列化器（用于查询/展示）"""
    username = serializers.CharField(source='user.nickname', read_only=True, label="姓名")
    device_name = serializers.CharField(source='device.device_name', read_only=True, label="设备名称")
    device_address = serializers.CharField(source='device.device_address', read_only=True, label="设备地址")
    dept_name = serializers.CharField(source='user.dept.dept_name', read_only=True, label="所属部门")

    class Meta:
        model = AttendanceRecord
        fields = "__all__"
        read_only_fields = ["id"]

    def get_time_stamp_str(self, obj):
        """格式化考勤时间（复用用户模块的时间格式化风格）"""
        return obj.time_stamp.strftime("%Y-%m-%d %H:%M:%S") if obj.time_stamp else None


class AttendanceRecordCreateSerializer(CustomModelSerializer):
    """考勤记录-创建序列化器（用于上传数据入库）"""
    # 新增：显式声明需要校验的字段（解决AssertionError）
    time = serializers.IntegerField(write_only=True, label="时间戳")  # 前端传的时间戳
    cmd = serializers.CharField(write_only=True, label="命令类型", allow_blank=True, required=False)

    class Meta:
        model = AttendanceRecord
        read_only_fields = ["id", "user", "device", "time_stamp", "command", "img_address"]

    def validate_time(self, value):
        """校验并转换时间戳为datetime"""
        try:
            return datetime.fromtimestamp(value)
        except Exception as e:
            raise serializers.ValidationError(f"时间戳转换失败：{str(e)}")



class AttendanceRecordResource(resources.ModelResource):
    class Meta:
        model = AttendanceRecord
        fields = (
            'id',
            'user__nickname',
            'device__device_name',
            'device__device_address',
            'time_stamp',
            'img_address'
        )
        export_order = fields
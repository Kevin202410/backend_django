import traceback

from app_attendance_record import serializers
# Create your views here.
from app_attendance_record.models import AttendanceRecord
from app_attendance_record.serializers import AttendanceRecordSerializer, AttendanceRecordCreateSerializer
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from utils.json_response import ErrorResponse, DetailResponse
from utils.viewset import CustomModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from app_user.models import Users
from app_device.models import Devices
from utils.common import base64_to_file, formatdatetime
from django.utils import timezone
from datetime import datetime

class AttendanceRecordViewSet(CustomModelViewSet):
    queryset = AttendanceRecord.objects.all()
    # 过滤/搜索/排序配置（修正字段匹配模型）
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user', 'device', 'status', 'time_stamp']  # 仅保留模型存在的字段
    search_fields = ['user__username', 'device__device_name', 'command']  # 关联字段搜索
    ordering_fields = ['time_stamp', 'status', 'user__username']
    ordering = ("-time_stamp",)
    # 序列化器映射（区分创建/默认场景）
    serializer_class = AttendanceRecordSerializer
    create_serializer_class = AttendanceRecordCreateSerializer
    http_method_names = ["get","post"]

    def get_queryset(self):
        """优化查询集：预加载关联数据，减少数据库查询"""
        queryset = super().get_queryset()
        # select_related 预加载外键（一对一/多对一）
        queryset = queryset.select_related(
            "user", "user__dept", "device"
        )
        return queryset

    def _match_user_and_device(self, user_id, sn):
        """私有方法：匹配用户和设备（对齐用户模块的关联数据匹配逻辑）"""
        user = None
        device = None
        # 匹配用户（按身份证号/工号）
        if user_id:
            user = Users.objects.filter(id=user_id, is_delete=0).first()
        # 匹配设备（按SN码）
        if sn:
            device = Devices.objects.filter(sn_code=sn, is_delete=0).first()
        return user, device

    @action(methods=["POST"], detail=False, permission_classes=[AllowAny])
    def up_record(self, request, *args, **kwargs):
        """
        考勤记录上传接口（完善逻辑：参数校验→数据匹配→图片处理→事务入库→统一响应）
        入参格式：{'body': {'image': base64_str, 'jobnumber': str, 'name': str, 'time': int, 'type': int}, 'cmd': str, 'sn': str}
        """
        try:
            # 1. 基础参数校验（对齐用户模块的参数校验风格）
            if not request.data:
                return ErrorResponse(code=400, msg="请求参数不能为空")

            # 解析嵌套参数
            body = request.data.get('body', {})
            cmd = request.data.get('cmd', '')
            sn = request.data.get('sn', '')
            user_id = int(body.get('jobnumber', ''))
            time_stamp = body.get('time', 0)
            image_base64 = body.get('image', '')
            # 核心参数校验
            if not user_id or not sn or not time_stamp:
                return ErrorResponse(code=400, msg="jobnumber、sn、time为必传参数")


            # 3. 匹配用户和设备
            user, device = self._match_user_and_device(user_id, sn)
            if not user:
                return ErrorResponse(code=404, msg=f"未找到ID为【{user_id}】的用户")
            if not device:
                return ErrorResponse(code=404, msg=f"未找到SN码为【{sn}】的设备")

            time_stamp = datetime.fromtimestamp(time_stamp)

            # 图片保存+考勤记录入库
            img_file = None
            if image_base64:
                img_file = base64_to_file(
                    base64_str=image_base64,
                    file_name=f"{user_id}_{time_stamp.strftime('%Y%m%d%H%M%S')}.jpg"
                )


            # 构建考勤记录数据
            record_data = {
                'user': user,
                'device': device,
                'time_stamp': formatdatetime(time_stamp),
                'command': cmd
            }
            # 保存图片（如果有）
            if img_file:
                record_data['img_address'] = img_file

            # 入库（对齐用户模块的创建逻辑）
            record = AttendanceRecord.objects.create(**record_data)

            # 5. 统一响应格式（对齐用户模块的DetailResponse）
            return DetailResponse(
                data={"record_id": record.id},
                msg="考勤记录上传成功"
            )

        except Exception as e:
            # 全局异常捕获（对齐用户模块的异常处理）
            traceback.print_exc()
            return ErrorResponse(code=500, msg=f"考勤记录上传失败：{str(e)}")



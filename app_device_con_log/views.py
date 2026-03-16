from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from app_device_con_log.models import DeviceConLog
from app_device_con_log.serializers import (
    DeviceConLogSerializer
)
from utils.json_response import DetailResponse, ErrorResponse
from utils.viewset import CustomModelViewSet
from utils.common import parse_excel_file, DEVICE_EXCEL_HEADER_MAP

# =====================================================
# 设备连接日志视图集
# =====================================================
class DeviceConLogViewSet(CustomModelViewSet):
    """
    设备连接日志接口
    """
    queryset = DeviceConLog.objects.all().order_by('-offline_time')
    serializer_class = DeviceConLogSerializer
    create_serializer_class = DeviceConLogSerializer
    update_serializer_class = DeviceConLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['sn_code']

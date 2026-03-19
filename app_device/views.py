from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from app_device.models import Devices
from app_device.serializers import (
    DeviceSerializer, DeviceCreateSerializer, DeviceResource
)
from utils.json_response import DetailResponse, ErrorResponse
from utils.viewset import CustomModelViewSet
from utils.common import parse_excel_file, DEVICE_EXCEL_HEADER_MAP, get_login_data
from django.views import View
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
# =====================================================
# 设备管理视图集
# =====================================================
class DeviceViewSet(CustomModelViewSet):
    """
    门禁设备管理接口
    增删改查 | 导入导出 | 状态自动更新
    """
    queryset = Devices.objects.filter(is_delete=False).order_by('sort')
    serializer_class = DeviceSerializer
    create_serializer_class = DeviceCreateSerializer
    update_serializer_class = DeviceCreateSerializer

    # 搜索/过滤配置
    search_fields = ['device_name', 'device_address', 'sn_code']
    filterset_fields = ['status', 'dept']
    permission_classes = [IsAuthenticated]

    @action(methods=["POST"], detail=False)
    def import_from_excel(self, request):
        """
        设备批量导入Excel
        """
        if 'file' not in request.FILES:
            return ErrorResponse(msg="请上传Excel文件")

        file = request.FILES['file']
        try:
            # 解析Excel
            excel_data = parse_excel_file(file)
            if not excel_data:
                return ErrorResponse(msg="Excel文件中无有效数据")

            success_count = 0
            fail_count = 0
            fail_details = []
            headers = list(DEVICE_EXCEL_HEADER_MAP.keys())

            # 遍历导入数据
            for row_num, row_data in enumerate(excel_data, start=2):
                row_dict = {}
                # 字段映射
                for col_idx, header in enumerate(headers):
                    field = DEVICE_EXCEL_HEADER_MAP[header]
                    val = row_data[col_idx] if col_idx < len(row_data) else None
                    if val:
                        row_dict[field] = val
                try:
                    serializer = self.create_serializer_class(data=row_dict)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    fail_details.append({
                        "行号": row_num,
                        "数据": row_data,
                        "错误": str(e)[:100]
                    })

            return DetailResponse(data={
                "success_count": success_count,
                "fail_count": fail_count,
                "fail_details": fail_details
            }, msg=f"导入完成：成功{success_count}条，失败{fail_count}条")

        except Exception as e:
            return ErrorResponse(msg=f"导入失败：{str(e)}")

    @action(methods=["GET"], detail=False)
    def export_to_excel(self, request):
        """
        设备数据导出Excel
        """
        resource = DeviceResource()
        dataset = resource.export()
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        filename = f"门禁设备_{timestamp}.xls"

        response = HttpResponse(
            dataset.xls,
            content_type="application/vnd.ms-excel"
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

@method_decorator(csrf_exempt, name='dispatch')
class DeviceLoginView(APIView):
    """
    设备登录路由视图
    路由：device/login
    功能：返回设备MQTT登录所需的配置参数
    """
    permission_classes = [AllowAny]
    def post(self, request):

        try:
            # 1. 获取设备序列号（sn）：从查询参数中获取（必填）
            sn = request.data.get('sn')
            if not sn:
                raise ValidationError("设备序列号（sn）不能为空")

            # 2. 从当前域名构造基础URL
            base_url = request.get_host()
            # 补全HTTP协议（避免URL缺失协议头）
            if not base_url.startswith(('http://', 'https://')):
                base_url = f"http://{base_url}"

            # 3. 构造响应数据（严格按需求格式，配置从settings读取）
            response_data = get_login_data(base_url, sn)
            print(f"设备【{sn}】获取MQTT登录配置成功")
            return JsonResponse(response_data, status=200)

        except ValidationError as e:
            # 参数校验失败返回错误响应
            print(f"设备登录配置获取失败：{str(e)}")
            return JsonResponse({
                "code": 400,
                "msg": str(e),
                "data": None
            }, status=400)
        except Exception as e:
            # 未知异常返回服务器错误
            print(f"设备登录配置获取异常：{str(e)}")
            return JsonResponse({
                "code": 500,
                "msg": "服务器内部错误",
                "data": None
            }, status=500)
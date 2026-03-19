
# Create your views here.
from app_attendance_record.models import AttendanceRecord
from app_attendance_record.serializers import AttendanceRecordSerializer, AttendanceRecordCreateSerializer
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from utils.viewset import CustomModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
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
    http_method_names = ["get","post","delete","put","patch"]

    def get_queryset(self):
        """优化查询集：预加载关联数据，减少数据库查询"""
        queryset = super().get_queryset()
        # select_related 预加载外键（一对一/多对一）
        queryset = queryset.select_related(
            "user", "user__dept", "device"
        )
        return queryset

    @action(methods=["POST"], detail=False, permission_classes=[AllowAny])
    def up_record(self, request, *args, **kwargs):
        # 处理上传的考勤数据
        print(request.data)
        # 示例：返回成功响应
        return Response({"message": "record received"}, status=200)


    # 可选：新增Excel导出action（复刻原有模块风格）
    # def export_to_excel(self, request):
    #     """考勤记录Excel导出"""
    #     # 实现导出逻辑（复用仓库原有导出工具）
    #     pass
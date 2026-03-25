from django.urls import path, include
from rest_framework import routers
from app_attendance_record.views import AttendanceRecordViewSet
from rest_framework.permissions import AllowAny

# 1. 路由注册（保持和用户/设备模块一致的命名风格）
system_router = routers.SimpleRouter()
# 注册考勤记录视图集（路由前缀：attendance-record，语义化命名）
system_router.register(r'upRecord', AttendanceRecordViewSet)

# 2. 自定义action路由（严格复刻原有格式）
urlpatterns = [
    # 考勤记录Excel导出（示例：复用原有action写法）
    # path('record/export_to_excel/', AttendanceRecordViewSet.as_view({'get': 'export_to_excel'})),
    path('upRecord', AttendanceRecordViewSet.as_view({'post': 'up_record'}, permission_classes=[AllowAny])),
]

# 3. 拼接自动生成的路由（和原有模块格式一致）
urlpatterns += system_router.urls
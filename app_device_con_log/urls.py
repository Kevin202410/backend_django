from django.urls import path
from rest_framework import routers


from app_device_con_log.views import DeviceConLogViewSet

# 1. 路由注册（和用户模块格式完全一致）
system_url = routers.SimpleRouter()
# 注册设备连接日志视图集
system_url.register(r'conlog', DeviceConLogViewSet)

# 2. 自定义action单独编写path（严格复刻用户模块的格式、缩进、命名）
urlpatterns = [
    # 设备连接日志Excel导出
    # path('device/export_to_excel/', DeviceConLogViewSet.as_view({'get': 'export_to_excel'}))
]

# 3. 拼接自动生成的路由（和用户模块一致）
urlpatterns += system_url.urls
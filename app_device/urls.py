from django.urls import path
from rest_framework import routers


from app_device.views import DeviceViewSet, DeviceLoginView

# 1. 路由注册（和用户模块格式完全一致）
system_url = routers.SimpleRouter()
# 注册设备主视图集
system_url.register(r'list', DeviceViewSet)

# 2. 自定义action单独编写path（严格复刻用户模块的格式、缩进、命名）
urlpatterns = [
    # 设备Excel导出
    path('list/export_to_excel/', DeviceViewSet.as_view({'get': 'export_to_excel'})),
    # 设备Excel导入
    path('list/import_from_excel/', DeviceViewSet.as_view({'post': 'import_from_excel'})),
    path('login/', DeviceLoginView.as_view()),
]

# 3. 拼接自动生成的路由（和用户模块一致）
urlpatterns += system_url.urls
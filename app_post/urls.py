
from django.urls import path
from rest_framework import routers

from app_post.views import PostViewSet

system_url = routers.SimpleRouter()
system_url.register(r'post', PostViewSet)

urlpatterns = [
    path('post/get-all-posts/', PostViewSet.as_view({'get': 'get_all_posts'})),
    path('post/export_to_excel/', PostViewSet.as_view({'get': 'export_to_excel'}))
]
urlpatterns += system_url.urls
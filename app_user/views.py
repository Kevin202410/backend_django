from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from app_menu.models import Menu
from app_menu.serializer import  MenuSerializer
from app_user.models import Users
from app_user.serializers import UserSerializer, UserCreateSerializer, UserResource
from utils.json_response import DetailResponse, ErrorResponse
from utils.viewset import CustomModelViewSet
from utils.common import parse_excel_file, USER_EXCEL_HEADER_MAP  # 导入Excel解析工具
import traceback

class UserViewSet(CustomModelViewSet):
    queryset = Users.objects.exclude(is_delete=1).all()
    serializer_class = UserSerializer
    create_serializer_class = UserCreateSerializer
    update_serializer_class = UserCreateSerializer
    filterset_fields = ['status', 'phone', 'role', 'dept']
    search_fields = ["username", "nickname"]

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def import_from_excel(self, request):
        """
        批量导入用户（Excel文件）
        请求参数：file（Excel文件）
        返回：导入结果（成功数、失败数、失败详情）
        """
        # 1. 校验文件是否上传
        if 'file' not in request.FILES:
            return ErrorResponse(code=400, msg="请上传Excel文件")

        file = request.FILES['file']
        try:
            # 2. 解析Excel文件
            excel_data = parse_excel_file(file)
            if not excel_data:
                return ErrorResponse(code=400, msg="Excel文件无有效数据")

            # 3. 数据转换与校验
            success_count = 0
            fail_count = 0
            fail_details = []

            for row_idx, row_data in enumerate(excel_data, start=2):  # 行号从2开始（跳过表头）
                row_dict = {}
                # 映射Excel列数据到字段（按表头顺序）
                headers = list(USER_EXCEL_HEADER_MAP.keys())
                for col_idx, header in enumerate(headers):
                    field = USER_EXCEL_HEADER_MAP[header]
                    value = row_data[col_idx] if col_idx < len(row_data) else None

                    # 特殊字段处理
                    if field == 'role' and value:
                        # 角色ID转列表（多个用,分隔）
                        row_dict[field] = [int(r.strip()) for r in str(value).split(',') if r.strip()]
                    elif field == 'post' and value:
                        # 岗位ID转列表
                        row_dict[field] = [int(p.strip()) for p in str(value).split(',') if p.strip()]
                    elif value is not None and value != '':
                        row_dict[field] = value

                # 4. 序列化校验并创建用户
                try:
                    serializer = UserCreateSerializer(data=row_dict)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    fail_details.append({
                        "row": row_idx,
                        "data": row_data,
                        "error": str(e),
                        "traceback": traceback.format_exc()[:200]  # 截断异常栈，避免返回过长
                    })

            # 5. 返回导入结果
            return DetailResponse(data={
                "success_count": success_count,
                "fail_count": fail_count,
                "fail_details": fail_details
            }, msg=f"导入完成：成功{success_count}条，失败{fail_count}条")

        except Exception as e:
            return ErrorResponse(code=500, msg=f"导入失败：{str(e)}")

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated])
    def auth(self, request):
        """
        获取用户权限信息
        """
        user = request.user

        result = {}
        result['user'] = {
            "userId": user.id,
            "username": user.username,
            "nickName": user.nickname,
            "phone": user.phone,
            "gender": user.gender,
            "email": user.email,
            "avatar": user.avatar,
            "dept": user.dept_id,
            "remark": user.remark,
            "is_superuser": user.is_superuser,
        }
        role = getattr(user, 'role')
        role_info = role.values('id', 'role_name', 'role_key')
        if role_info:
            result['role'] = role_info[0]
        else:
            return ErrorResponse(code=4003, msg="该用户没有设定角色，请联系管理员分配角色")
        # 获取对应的menus
        is_superuser = request.user.is_superuser
        is_admin = request.user.role.values_list('admin', flat=True)
        if is_superuser or True in is_admin:
            queryset = Menu.objects.filter(status='0').all()
        else:
            menu_id_list = request.user.role.values_list('menu', flat=True)
            queryset = Menu.objects.filter(status='0', id__in=menu_id_list)

        menu_serializers = MenuSerializer(queryset, many=True).data

        permissions = []
        menus = []
        for menu_serializer in menu_serializers:
            is_hide = menu_serializer['is_hide']
            is_keep_alive = menu_serializer['is_keep_alive']
            is_affix = menu_serializer['is_affix']
            is_iframe = menu_serializer['is_iframe']
            permission = menu_serializer['permission']
            menu_type = menu_serializer['menu_type']
            menu = {
                "id": menu_serializer['id'],
                "parent_id": menu_serializer['parent'],
                "name": menu_serializer['path'],
                "path": menu_serializer['path'],
                "redirect": '',
                "component": menu_serializer['component'],
                "meta": {
                    "title": menu_serializer['menu_name'],
                    "isLink": menu_serializer['is_link'],
                    "isHide": False if is_hide == '0' else True,
                    "isKeepAlive": False if is_keep_alive == '1' else True,
                    "isAffix": False if is_affix == '1' else True,
                    "isIframe": False if is_iframe == '1' else True,
                    "auth": [] if permission == '' else [permission],
                    "icon": menu_serializer['icon']
                },
                'children': []
            }
            if menu_type != 'F':
                menus.append(menu)
            if menu_type in ['F', 'C']:
                permissions.append(permission)

        res_p = []
        # 创建数据字典
        data_dict = {item["id"]: item for item in menus}

        # 遍历数据，找出最高级节点（parent_id为None）
        for item in menus:
            if item["parent_id"] is None:
                res_p.append(item)

        # 递归构建树形结构
        def build_tree(node, data_dict):
            node["children"] = [
                build_tree(data_dict[child_id], data_dict)
                for child_id in data_dict
                if data_dict[child_id]["parent_id"] == node["id"]
            ]
            return node

        # 构建树形结构
        for item in res_p:
            build_tree(item, data_dict)

        result['menus'] = res_p
        result['permissions'] = permissions
        return DetailResponse(data=result, msg="获取成功")

    def user_info(self, request):
        """
        获取当前用户信息
        """
        user = request.user
        result = {
            "nickname": user.nickname,
            "phone": user.phone,
            "gender": user.gender,
            "email": user.email
        }
        return DetailResponse(data=result, msg="获取成功")

    def update_user_info(self, request):
        """
        修改当前用户信息
        """
        user = request.user
        Users.objects.filter(id=user.id).update(**request.data)
        return DetailResponse(data=None, msg="修改成功")

    def export_to_excel(self, request):
        """
        用户表导出
        """
        user_resource = UserResource()
        dataset = user_resource.export()
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        filename = f"user_{timestamp}.xls"
        response = HttpResponse(dataset.xls, content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
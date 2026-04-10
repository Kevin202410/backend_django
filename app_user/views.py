import traceback
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from app_menu.models import Menu
from app_menu.serializer import MenuSerializer
from app_user.models import Users
from app_user.serializers import UserSerializer, UserCreateSerializer, UserResource, UserAvatarSerializer
from utils.json_response import DetailResponse, ErrorResponse
from utils.viewset import CustomModelViewSet
from utils.common import (
    parse_excel_file, USER_EXCEL_HEADER_MAP, delete_old_file,
    process_image, extract_zip_file, rewrite_image_url, get_full_image_url, renameuploadimg
)

class UserViewSet(CustomModelViewSet):
    queryset = Users.objects.exclude(is_delete=1)
    serializer_class = UserSerializer
    create_serializer_class = UserCreateSerializer
    update_serializer_class = UserCreateSerializer
    filterset_fields = ['status', 'phone', 'role', 'dept']
    search_fields = ["username", "nickname", "id_card"]
    parser_classes = (MultiPartParser, FormParser, JSONParser)  # 支持文件上传解析器

    def _get_user_avatar_url(self, request, user):
        """抽取私有方法：获取用户完整头像URL（复用代码）"""
        if not user.avatar:
            return None
        relative_url = rewrite_image_url(request, user.avatar.url)
        return get_full_image_url(request, relative_url)

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def import_from_excel(self, request):
        """Excel批量导入用户"""
        if 'file' not in request.FILES:
            return ErrorResponse(msg="请上传Excel文件")

        try:
            excel_data = parse_excel_file(request.FILES['file'])
            if not excel_data:
                return ErrorResponse(msg="Excel文件无有效数据")

            success_count = fail_count = 0
            fail_details = []
            headers = list(USER_EXCEL_HEADER_MAP.keys())

            for row_idx, row_data in enumerate(excel_data, start=2):
                row_dict = {}
                # 字段映射
                for col_idx, header in enumerate(headers):
                    field = USER_EXCEL_HEADER_MAP[header]
                    val = row_data[col_idx] if col_idx < len(row_data) else None
                    if val:
                        row_dict[field] = val

                # 校验并创建用户
                try:
                    serializer = UserCreateSerializer(data=row_dict)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    fail_details.append({
                        "行号": row_idx, "数据": row_data, "错误": str(e)[:100]
                    })

            return DetailResponse(data={
                "成功数": success_count, "失败数": fail_count, "失败详情": fail_details
            }, msg=f"导入完成：成功{success_count}条，失败{fail_count}条")

        except Exception as e:
            return ErrorResponse(msg=f"导入失败：{str(e)}")

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def batch_import_avatar(self, request):
        """
        批量导入用户头像（zip压缩包，内为「身份证号码.图片后缀」的文件）
        取消事务回滚，生成真实导入结果报告：成功数、失败数、失败详情
        文件名与单个上传保持统一
        """
        current_user = request.user
        # 1. 管理员权限校验
        is_superuser = current_user.is_superuser
        is_admin = current_user.role.filter(admin=True).exists()
        if not (is_superuser or is_admin):
            return ErrorResponse(code=403, msg="仅管理员可批量导入头像")

        # 2. 校验压缩包
        if 'file' not in request.FILES:
            return ErrorResponse(code=400, msg="请上传zip压缩包文件")
        zip_file = request.FILES['file']
        if not zip_file.name.lower().endswith('.zip'):
            return ErrorResponse(code=400, msg="仅支持zip格式的压缩包")

        try:
            # 3. 解压压缩包
            id_card_image_map = extract_zip_file(zip_file)
            if not id_card_image_map:
                return ErrorResponse(code=400, msg="压缩包内无有效图片文件")

            success_count = 0
            fail_count = 0
            fail_details = []

            # ===================== 已取消事务，支持部分成功导入 =====================
            for id_card, img_file in id_card_image_map.items():
                try:
                    # 匹配用户
                    user = Users.objects.exclude(is_delete=1).get(id_card=id_card)
                    # 图片标准化处理（转JPG、高1024、≤1M）
                    processed_img = process_image(img_file)

                    # 文件名与单个上传保持统一
                    processed_img.name = renameuploadimg(processed_img.name)

                    # 删除旧头像文件
                    if user.avatar:
                        delete_old_file(user.avatar.path)
                    # 保存新头像
                    user.avatar = processed_img
                    user.save(update_fields=['avatar'])
                    success_count += 1

                except Users.DoesNotExist:
                    fail_count += 1
                    fail_details.append({
                        "id_card": id_card,
                        "error": "未找到对应用户"
                    })
                except Exception as e:
                    fail_count += 1
                    fail_details.append({
                        "id_card": id_card,
                        "error": str(e)[:100]  # 截断错误信息
                    })

            # 返回真实导入结果报告
            return DetailResponse(data={
                "success_count": success_count,
                "fail_count": fail_count,
                "fail_details": fail_details
            }, msg=f"批量导入头像完成：成功 {success_count} 个，失败 {fail_count} 个")

        except Exception as e:
            return ErrorResponse(code=500, msg=f"批量导入失败：{str(e)}")

    @action(methods=["POST"], detail=True, permission_classes=[IsAuthenticated])
    def upload_avatar(self, request, pk=None):
        """
        单个用户头像上传（支持当前用户/管理员操作）
        - detail=True：需要传入用户ID(pk)
        - 管理员可更新任意用户头像，普通用户只能更新自己的头像
        """
        # 获取目标用户
        target_user = self.get_object()
        current_user = request.user

        # 权限校验：普通用户只能更新自己的头像
        if not (current_user.is_superuser or
                current_user.role.filter(admin=True).exists() or
                current_user.id == target_user.id):
            return ErrorResponse(code=403, msg="您无权修改此用户头像")

        # 校验文件是否上传
        if 'avatar' not in request.FILES:
            return ErrorResponse(msg="请上传头像文件")

        try:
            # 1. 获取上传文件并处理
            avatar_file = request.FILES['avatar']
            serializer = UserAvatarSerializer(
                instance=target_user,
                data={'avatar': avatar_file},
                context={'request': request},
                partial=True  # 支持部分更新
            )

            # 2. 序列化校验（复用已有的文件格式/大小校验）
            serializer.is_valid(raise_exception=True)

            # 3. 事务处理：删除旧头像→处理新头像→保存
            with transaction.atomic():
                # 删除旧头像文件
                if target_user.avatar:
                    delete_old_file(target_user.avatar.path)

                # 图片标准化处理（转JPG、等比缩放、压缩至1M内）
                processed_avatar = process_image(avatar_file)

                processed_avatar.name = renameuploadimg(processed_avatar.name)

                # 4. 保存新头像
                target_user.avatar = processed_avatar
                target_user.save(update_fields=['avatar', 'update_datetime'])

            # 5. 返回处理后的完整头像URL
            return DetailResponse(data={
                "id": target_user.id,
                "nickname": target_user.nickname,
                "avatar_url": self._get_user_avatar_url(request, target_user),
                "msg": "头像上传成功"
            })

        except Exception as e:
            return ErrorResponse(msg=f"头像上传失败：{str(e)}")

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated])
    def auth(self, request):
        """获取用户权限+菜单+头像信息"""
        user = request.user
        # 整合头像URL
        result = {"user": {
            "userId": user.id,
            "username": user.username,
            "nickName": user.nickname,
            "phone": user.phone,
            "gender": user.gender,
            "email": user.email,
            "avatar": self._get_user_avatar_url(request, user),
            "dept": user.dept_id,
            "remark": user.remark,
            "is_superuser": user.is_superuser,
        }}

        # 角色校验
        role_info = user.role.values('id', 'role_name', 'role_key').first()
        if not role_info:
            return ErrorResponse(code=4003, msg="请先为用户分配角色")
        result['role'] = role_info

        # 菜单权限
        is_admin = user.is_superuser or user.role.filter(admin=True).exists()
        menu_qs = Menu.objects.filter(status='0')
        if not is_admin:
            menu_qs = menu_qs.filter(id__in=user.role.values_list('menu', flat=True))

        # 菜单树形结构
        menu_data = MenuSerializer(menu_qs, many=True).data
        permissions, menus = [], []
        for item in menu_data:
            menu = {
                "id": item['id'], "parent_id": item['parent'], "name": item['path'],
                "path": item['path'], "component": item['component'],
                "meta": {
                    "title": item['menu_name'], "icon": item['icon'],
                    "isLink": item['is_link'], "isHide": item['is_hide'] != '0',
                    "isKeepAlive": item['is_keep_alive'] == '1',
                    "isAffix": item['is_affix'] == '1',
                    "isIframe": item['is_iframe'] == '1',
                    "auth": [item['permission']] if item['permission'] else []
                }, "children": []
            }
            if item['menu_type'] != 'F':
                menus.append(menu)
            if item['menu_type'] in ['F', 'C']:
                permissions.append(item['permission'])

        # 构建树形菜单
        data_dict = {i["id"]: i for i in menus}
        def build_tree(node):
            node["children"] = [build_tree(data_dict[cid]) for cid in data_dict if data_dict[cid]["parent_id"] == node["id"]]
            return node
        tree_menus = [build_tree(n) for n in menus if n["parent_id"] is None]

        result['menus'] = tree_menus
        result['permissions'] = permissions
        return DetailResponse(data=result)

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated])
    def user_info(self, request):
        """获取当前用户信息"""
        user = request.user
        return DetailResponse(data={
            "nickname": user.nickname, "phone": user.phone, "gender": user.gender,
            "email": user.email, "avatar": self._get_user_avatar_url(request, user)
        })

    @action(methods=["POST"], detail=False, permission_classes=[IsAuthenticated])
    def update_user_info(self, request):
        """修改当前用户信息"""
        Users.filter(id=request.user.id).update(**request.data)
        return DetailResponse(msg="修改成功")

    @action(methods=["GET"], detail=False, permission_classes=[IsAuthenticated])
    def export_to_excel(self, request):
        """导出用户数据"""
        dataset = UserResource().export()
        filename = f"user_{timezone.now().strftime('%Y%m%d%H%M%S')}.xls"
        response = HttpResponse(dataset.xls, content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
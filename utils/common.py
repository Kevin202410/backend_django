# ------------------------------
# 公用方法
# ------------------------------
#/utils/common.py
import os
import re
import io
import random
import time
import ast
import base64
import hashlib
import json
import zipfile
import os.path as op
import datetime
from urllib.parse import urlparse
from io import BytesIO
from PIL import Image
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from rest_framework.request import Request
from django.http import QueryDict
from rest_framework.exceptions import ValidationError
import openpyxl
import xlrd

# ------------------------------
# 正则常量
# ------------------------------
# 手机号验证正则（统一正则，避免重复定义）
REGEX_MOBILE = re.compile(r"^1[356789]\d{9}$|^147\d{8}$|^176\d{8}$")

# ------------------------------
# Excel配置
# ------------------------------
# 定义Excel表头与字段的映射关系
USER_EXCEL_HEADER_MAP = {
    '用户名': 'username',
    '姓名': 'nickname',
    '身份证号': 'id_card',
    '手机号(选填)': 'phone',
    '邮箱(选填)': 'email'
}

DEVICE_EXCEL_HEADER_MAP = {
    '门禁名称': 'device_name',
    '门禁位置': 'device_address',
    'SN': 'sn_code',
    '排序': 'sort'
}

# ------------------------------
# 图片处理配置
# ------------------------------
TARGET_HEIGHT = 1024  # 目标高度
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1M 上限
TARGET_FORMAT = 'JPEG'  # 强制转换为JPG
TARGET_EXT = '.jpg'

# ------------------------------
# Excel解析
# ------------------------------
def parse_excel_file(file, sheet_name=None):
    """
    解析Excel文件，返回二维列表数据
    :param file: 上传的文件对象
    :param sheet_name: 指定sheet名称（默认第一个）
    :return: list[list] 解析后的数据（跳过表头）
    """
    try:
        # 处理.xlsx格式
        if file.name.endswith('.xlsx'):
            wb = openpyxl.load_workbook(BytesIO(file.read()), data_only=True)
            sheet = wb[sheet_name] if sheet_name else wb.active
            data = []
            for row in sheet.iter_rows(min_row=2, values_only=True):  # 跳过表头（第一行）
                if any(cell is not None for cell in row):  # 跳过空行
                    data.append(list(row))
            return data
        # 处理.xls格式
        elif file.name.endswith('.xls'):
            wb = xlrd.open_workbook(file_contents=file.read())
            sheet = wb.sheet_by_name(sheet_name) if sheet_name else wb.sheet_by_index(0)
            data = []
            for row_idx in range(1, sheet.nrows):  # 跳过表头
                row = sheet.row_values(row_idx)
                if any(cell is not None and cell != '' for cell in row):
                    data.append(row)
            return data
        else:
            raise ValidationError("仅支持.xlsx/.xls格式的Excel文件")
    except Exception as e:
        raise ValidationError(f"Excel解析失败：{str(e)}")

# ------------------------------
# 时间格式化
# ------------------------------
def format_wechat_gmt_8_to_normal(wgmt8):
    """
    微信GMT+8 转换成标准时间字符串
    wgmt8:2022-01-12T16:35:42+08:00
    return:2022-01-12 16:35:42
    """
    try:
        a1 = wgmt8.split('T')
        a2 = a1[1].split('+')
        a3 = a1[0] + ' ' + a2[0]
        return a3
    except Exception:
        return wgmt8

def formatdatetime(datatimes):
    """
    格式化日期时间为指定格式
    :param datatimes: 数据库中存储的datetime日期时间/字符串
    :return: 格式化后的日期时间：2021-09-23 11:22:03
    """
    if not datatimes:
        return datatimes
    try:
        if isinstance(datatimes, str):
            return datatimes.split(".")[0] if "." in datatimes else datatimes
        return datatimes.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return datatimes

def formatdatetime_convert(datatimes):
    """
    格式化字符串日期为Python datetime对象（修复原代码变量错误）
    :param datatimes: 字符串(2021-09-23 11:22:03 / 2021-09-23)
    :return: datetime对象
    """
    if not datatimes or not isinstance(datatimes, str):
        return datatimes
    try:
        fmt = '%Y-%m-%d %H:%M:%S' if ':' in datatimes else '%Y-%m-%d'
        return datetime.datetime.strptime(datatimes, fmt)
    except Exception:
        return datatimes

# ------------------------------
# 随机字符串/邀请码/订单号
# ------------------------------
def getRandomSet(bits):
    """生成指定位数 数字+小写字母 随机字符串"""
    num_set = [chr(i) for i in range(48, 58)]
    char_set = [chr(i) for i in range(97, 123)]
    total_set = num_set + char_set
    return "".join(random.sample(total_set, bits))

def getinvitecode6():
    """随机生成6位大写邀请码:8614LY"""
    return getRandomSet(6).upper()

def getminrandomodernum():
    """生成短订单号"""
    basecode = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    chagecode1 = random.randint(10, 99)
    chagecode3 = str(time.time()).replace('.', '')[-7:]
    return f"{basecode}{chagecode1}{chagecode3}"

def getrandomodernum():
    """生成长订单号"""
    basecode = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    chagecode1 = random.randint(100, 999)
    chagecode2 = random.randint(10, 99)
    chagecode3 = str(time.time()).replace('.', '')[-7:]
    return f"{basecode}{chagecode1}{chagecode2}{chagecode3}"

# ------------------------------
# 手机号处理
# ------------------------------
def hide4mobile(mobile):
    """隐藏手机号中间四位"""
    if re.match(r"^\d{11}$", mobile):
        return mobile.replace(mobile[3:7], '****')
    return ""

def checkphonenum(phonenum):
    """验证是否为有效手机号（复用统一正则）"""
    if not phonenum:
        return False
    return bool(REGEX_MOBILE.match(phonenum))

# ------------------------------
# 数值/金额格式化
# ------------------------------
def float2dot(str_num):
    """数字转为保留两位小数的字符串"""
    try:
        return '%.2f' % round(float(str_num), 2)
    except:
        return str_num

def ismoney(num):
    """判断是否为正整数金额（不含0、小数点）"""
    try:
        if not num:
            return False
        val = int(num)
        return val > 0 and re.match(r'^[0-9]\d*$', str(num)) is not None
    except:
        return False

def isRealPrice(num):
    """判断是否为合法价格（正整数/两位小数、非0）"""
    try:
        if not num or num in (0, '0', ''):
            return False
        pattern = re.compile(r"(^[1-9]\d*$)|(^([1-9]\d*|0)(\.\d{1,2})?$)")
        return bool(pattern.match(str(num)))
    except:
        return False

# ------------------------------
# 文件/图片/URL处理
# ------------------------------
def renameuploadimg(srcimg):
    """自定义上传图片文件名：时间戳+随机数"""
    ext = os.path.splitext(srcimg)[1]
    ext = ext[:255] if len(srcimg) > 255 else ext
    fn = f"{time.strftime('%Y%m%d%H%M%S')}_{random.randint(100, 999)}"
    return fn + ext

def getfulldomian(requests):
    """获取请求完整域名（http/https + host）"""
    return '{scheme}://{host}'.format(scheme=requests.scheme, host=requests.get_host())

def geturlpath(url):
    """获取URL的path部分"""
    return urlparse(url).path

def rewrite_image_url(request, url):
    """重写图片URL为相对路径（适配服务器迁移）"""
    if url and '://' in url and '127.0.0.1' in url:
        return geturlpath(url)
    return url

def get_full_image_url(request, url):
    """获取图片完整URL（跨域可用）"""
    if not url:
        return url
    if 'http://' not in url and 'https://' not in url:
        return f"{getfulldomian(request)}{url}"
    return url

def delete_old_file(file_path):
    """删除旧文件（兼容相对/绝对路径）"""
    if not file_path:
        return
    if not op.isabs(file_path):
        file_path = op.join(settings.MEDIA_ROOT, file_path)
    if op.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"[失败] 删除旧文件 {file_path} 出错：{str(e)}")

def process_image(image_file, target_height=TARGET_HEIGHT, max_size=MAX_FILE_SIZE):
    """
    图片标准化处理：转JPG、等比缩放、压缩至1M内
    :param image_file: 上传的图片文件
    :return: 处理后的InMemoryUploadedFile
    """
    try:
        img = Image.open(image_file)
        # 处理透明通道/灰度图
        if img.mode in ('RGBA', 'P', 'L'):
            img = img.convert('RGB')

        # 等比缩放
        width, height = img.size
        ratio = target_height / height
        new_width = int(width * ratio)
        # 兼容PIL高低版本
        resample = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
        img = img.resize((new_width, target_height), resample=resample)

        # 动态压缩质量
        img_byte_arr = io.BytesIO()
        quality = 95
        while True:
            img_byte_arr.seek(0)
            img_byte_arr.truncate()
            img.save(img_byte_arr, format=TARGET_FORMAT, quality=quality, optimize=True)
            if img_byte_arr.tell() <= max_size or quality <= 10:
                break
            quality -= 5

        # 构建新文件对象
        new_name = f"{op.splitext(image_file.name)[0]}{TARGET_EXT}"
        return InMemoryUploadedFile(
            file=img_byte_arr,
            field_name=image_file.field_name,
            name=new_name,
            content_type=f'image/{TARGET_FORMAT.lower()}',
            size=img_byte_arr.tell(),
            charset=None
        )
    except Exception as e:
        raise Exception(f"图片处理失败：{str(e)}")

# ------------------------------
# 压缩包处理
# ------------------------------
def extract_zip_file(zip_file):
    """
    解压zip，返回 {身份证号: 图片文件对象} 映射
    :param zip_file: 上传的zip文件
    :return: dict
    """
    id_card_image_map = {}
    img_suffix = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')
    try:
        with zipfile.ZipFile(zip_file, 'r') as zf:
            for file_name in zf.namelist():
                # 过滤目录/非图片文件
                if file_name.endswith('/') or not file_name.lower().endswith(img_suffix):
                    continue
                # 提取身份证号（文件名去后缀）
                id_card = op.splitext(op.basename(file_name))[0].strip()
                if not id_card:
                    continue
                # 构建文件对象
                file_data = zf.read(file_name)
                img_file = InMemoryUploadedFile(
                    file=io.BytesIO(file_data),
                    field_name='avatar',
                    name=file_name,
                    content_type=f'image/{op.splitext(file_name)[1][1:].lower()}',
                    size=len(file_data),
                    charset=None
                )
                id_card_image_map[id_card] = img_file
        return id_card_image_map
    except Exception as e:
        raise Exception(f"解压压缩包失败：{str(e)}")

# ------------------------------
# 请求参数/IP处理
# ------------------------------
def get_parameter_dic(request, *args, **kwargs):
    """统一获取GET/POST参数"""
    if not isinstance(request, Request):
        return {}
    query_params = request.query_params.dict() if isinstance(request.query_params, QueryDict) else request.query_params
    result_data = request.data.dict() if isinstance(request.data, QueryDict) else request.data
    return query_params if query_params else result_data

def getrealip(request):
    """获取用户真实IP"""
    try:
        return request.META['HTTP_X_FORWARDED_FOR'].split(",")[0]
    except:
        return request.META.get('REMOTE_ADDR', "")

# ------------------------------
# 加密/类型转换
# ------------------------------
def bas64_encode_text(text):
    """base64加密字符串"""
    return str(base64.b64encode(text.encode('utf-8')), 'utf-8') if isinstance(text, str) else text

def bas64_decode_text(text):
    """base64解密字符串"""
    return str(base64.decodebytes(bytes(text, "utf8")), 'utf8') if isinstance(text, str) else text

def ly_md5(text):
    """MD5加密"""
    m = hashlib.md5()
    m.update(text.encode('utf-8'))
    return m.hexdigest()

def ast_convert(text):
    """字符串转列表/字典"""
    return ast.literal_eval(text) if text else None

def ast_convert_str(arr):
    """列表/字典转字符串"""
    if not arr:
        return None
    if isinstance(arr, (dict, list)):
        return json.dumps(arr, ensure_ascii=False)
    return str(arr)

def srttolist(str_data):
    """字符串列表转列表"""
    if not str_data:
        return []
    str1 = str_data.replace('[', '').replace(']', '').replace('"', '').replace("'", '')
    return str1.split(',') if str1 else []

def re_api(api):
    """提取API路径（去除参数）"""
    match = re.match(r'(/[^?]+)', api)
    return match.group(1) if match else api

def get_login_data(base_url, sn):
    response_data = {
        "cmd": "login",
        "url": f"{base_url}/attendance",
        "user": settings.MQTT_USERNAME,
        "pd": settings.MQTT_PASSWORD,
        "host": settings.MQTT_HOST,
        "port": int(settings.MQTT_PORT),
        "uploadTopic": f"cs/{sn}/events",
        "downTopic": f"cs/{sn}/msg",
        "clientID": sn,
        "keepalive": int(settings.MQTT_KEEPALIVE),
    }
    return response_data
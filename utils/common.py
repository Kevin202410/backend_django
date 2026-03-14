# ------------------------------
# 公用方法
# ------------------------------

import os, re, io
import random
import time
from rest_framework.request import Request
from django.http import QueryDict
from urllib.parse import urlparse
import datetime
import ast
import base64
import hashlib
import json
import openpyxl
import xlrd
from io import BytesIO
from rest_framework.exceptions import ValidationError
from PIL import Image
import zipfile
import os.path as op
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile

# 手机号验证正则
REGEX_MOBILE = "^1[356789]\d{9}$|^147\d{8}$|^176\d{8}$"

# 定义Excel表头与字段的映射关系
USER_EXCEL_HEADER_MAP = {
    '用户名': 'username',
    '姓名': 'nickname',
    '身份证号': 'id_card',
    '手机号(选填)': 'phone',
    '邮箱(选填)': 'email'
}

# 图片处理配置
TARGET_HEIGHT = 1024  # 目标高度
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1M 上限
TARGET_FORMAT = 'JPEG'  # 强制转换为JPG
TARGET_EXT = '.jpg'

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

# 微信GMT+8 转换成标准时间字符串
def format_wechat_gmt_8_to_normal(wgmt8):
    """
    wgmt8:2022-01-12T16:35:42+08:00
    return:2022-01-12 16:35:42
    """
    try:
        a1 = wgmt8.split('T')
        a2 = a1[1].split('+')
        a3 = a1[0] + ' ' + a2[0]
        return a3
    except Exception as e:
        return wgmt8


# 随机生成6位大写的邀请码:8614LY
def getinvitecode6():
    random_str = getRandomSet(6)
    return random_str.upper()


# 生成随机得指定位数字母+数字字符串
def getRandomSet(bits):
    """
    bits:数字是几就生成几位
    """
    num_set = [chr(i) for i in range(48, 58)]
    char_set = [chr(i) for i in range(97, 123)]
    total_set = num_set + char_set
    value_set = "".join(random.sample(total_set, bits))
    return value_set


def hide4mobile(mobile):
    """
    隐藏手机号中间四位
    """
    if re.match("^\d{11}$", mobile):
        list = mobile[3:7]
        new_phone = mobile.replace(list, '****')
        return new_phone
    else:
        return ""


def float2dot(str):
    """
    把数字或字符串10.00 转换成保留后两位（字符串）输出
    """
    try:
        return '%.2f' % round(float(str), 2)
    except:
        return str


"""
格式化日期时间为指定格式
"""


def formatdatetime(datatimes):
    """
    格式化日期时间为指定格式
    :param datatimes: 数据库中存储的datetime日期时间,也可以是字符串形式(2021-09-23 11:22:03.1232000)
    :return: 格式化后的日期时间如：2021-09-23 11:22:03
    """
    if datatimes:
        try:
            if isinstance(datatimes, str):
                if "." in datatimes:
                    arrays = datatimes.split(".", maxsplit=1)
                    if arrays:
                        return arrays[0]
            return datatimes.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            return datatimes
    return datatimes


def formatdatetime_convert(datatimes):
    """
    格式化字符串日期时间为 python的日期时间
    :param datatimes: 字符串形式(2021-09-23 11:22:03 或 2021-09-23)
    :return: 反格式化后的日期时间如：datetime.datetime(2021, 9, 23, 11, 22, 3)
    """
    if datatimes:
        try:
            if isinstance(datatimes, str):
                if ':' in datatimes:
                    return datetime.datetime.strptime('datatimes', '%Y-%m-%d %H:%M:%S')
                else:
                    return datetime.datetime.strptime('datatimes', '%Y-%m-%d')
        except Exception as e:
            return datatimes
    return datatimes


# 上传图片名自定义
"""
参数为图片文件名
"""


def renameuploadimg(srcimg):
    # 文件扩展名
    ext = os.path.splitext(srcimg)[1]
    # File names longer than 255 characters can cause problems on older OSes.
    if len(srcimg) > 255:
        ext = ext[:255]
    # 定义文件名，年月日时分秒随机数
    fn = time.strftime('%Y%m%d%H%M%S')
    fn = fn + '_%d' % random.randint(100, 999)
    # 重写合成文件名
    name = fn + ext
    return name


# 获取请求的域名包括http或https前缀如：https://www.xxx.cn
"""
参数requests为请求request
"""


def getfulldomian(requests):
    host = '{scheme}://{host}'.format(scheme=requests.scheme, host=requests.get_host())
    return host


"""
获取url地址中的path部分
"""


def geturlpath(url):
    # ParseResult(scheme='https', netloc='blog.xxx.net', path='/yilovexing/article/details/96432467', params='', query='', fragment='')
    all = urlparse(url)
    path = all.path
    return path


"""
重写数据库中的图片url前缀路径，返回相对路径的url路径，保证服务器更换环境导致图片访问失败情况
适用于图片存储在服务器本地
"""


def rewrite_image_url(request, url):
    """
    :param request: 用户请求request
    :param url: 图片url原路径
    :return: 图片url新路径
    """
    if '://' in url and 'http' in url and '127.0.0.1':

        fulldomain = getfulldomian(request)
        urlpath = geturlpath(url)
        # return fulldomain+urlpath
        return urlpath
    else:
        return url


def get_full_image_url(request, url):
    """
    :param request: 用户请求request
    :param url: 图片url原路径
    :return: 图片url新路径
    """
    if not url:
        return url
    elif 'http://' not in url and 'https://' not in url:

        fulldomain = getfulldomian(request)
        return fulldomain + url
    else:
        return url


# 验证是否为有效手机号
def checkphonenum(phonenum):
    mobile_pat = re.compile('^1([38]\d|5[0-35-9]|7[3678])\d{8}$')
    res = re.search(mobile_pat, phonenum)
    if res:
        return True
    else:
        return False


# 获取get 或 post的参数
# 使用方法：get_parameter_dic(request)['name'] ,name为获取的参数名 ,此种方式获取name不存在则会报错返回name表示name不存在，需要此参数
# get_parameter_dic(request).get('name') ,name为获取的参数名 ,此种方式获取name不存在不会报错，不存在会返回None
def get_parameter_dic(request, *args, **kwargs):
    if isinstance(request, Request) == False:
        return {}

    query_params = request.query_params
    if isinstance(query_params, QueryDict):
        query_params = query_params.dict()
    result_data = request.data
    if isinstance(result_data, QueryDict):
        result_data = result_data.dict()

    if query_params != {}:
        return query_params
    else:
        return result_data

"""
把字符串列表转换成列表类型
"""

def srttolist(str):
    # ['http://6fb77aa4dd1d.ngrok.io/media/tasks/2021-08-16/20210816103922_38.png']
    if str:
        str1 = str.replace('[', '').replace(']', '').replace("\"", '').replace("\'", '')
        str2 = str1.split(',')
        return str2
    else:
        return []

# 获取请求用户的真实ip地址
def getrealip(request):
    try:
        real_ip = request.META['HTTP_X_FORWARDED_FOR']
        regip = real_ip.split(",")[0]
    except:
        try:
            regip = request.META['REMOTE_ADDR']
        except:
            regip = ""
    return regip

# 生成订单号(短订单号)
def getminrandomodernum():
    basecode = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    chagecode1 = random.randint(10, 99)
    chagecode3 = str(time.time()).replace('.', '')[-7:]
    return str(basecode) + str(chagecode1) + chagecode3

# 生成订单号（长订单号）
def getrandomodernum():
    basecode = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    chagecode1 = random.randint(100, 999)
    chagecode2 = random.randint(10, 99)
    chagecode3 = str(time.time()).replace('.', '')[-7:]
    return str(basecode) + str(chagecode1) + str(chagecode2) + chagecode3

# 判断是否为金额(不包含0)，（正整数金额，不包含小数点）
def ismoney(num):
    try:
        pattern = re.compile(r'^[0-9]\d*$')
        if not num:
            return False
        val = int(num)
        if val <= 0:
            return False
        result = pattern.match(num)
        if result:
            return True
        else:
            return False
    except Exception as e:
        return False

# 判断是否为正确的价格（正整数、小数（小数点后两位）、非0）
def isRealPrice(num):
    try:
        if num == "" or num == None or num == 0 or num == '0':
            return False
        value = str(num)
        pattern = re.compile(r"(^[0-9]\d*$)|(^(([1-9]{1}\d*)|(0{1}))(\.\d{0,2})?$)")  # 正整数判断和小数判断
        result = pattern.match(value)
        if result:
            return True
        else:
            return False
    except Exception as e:
        return False

# 把字符串转换成数组对象等
def ast_convert(str):
    if str:
        try:
            myobject = ast.literal_eval(str)
            return myobject
        except Exception as e:
            return str

    return None

# 把数组对象转换成字符串转
def ast_convert_str(arr):
    if arr:
        try:
            if isinstance(arr, str):
                return arr
            if isinstance(arr, dict):
                return json.dumps(arr)
            if isinstance(arr, list):
                return json.dumps(arr)
        except Exception as e:
            return arr

    return None

def bas64_encode_text(text):
    """
    base64加密字符串
    :param text:
    :return:
    """
    if isinstance(text, str):
        return str(base64.b64encode(text.encode('utf-8')), 'utf-8')
    return text

def bas64_decode_text(text):
    """
    base64解密字符串
    :param text:
    :return:
    """
    if isinstance(text, str):
        return str(base64.decodebytes(bytes(text, encoding="utf8")), 'utf-8')
    return text

def ly_md5(str):
    m = hashlib.md5()
    m.update(str.encode(encoding='utf-8'))
    return m.hexdigest()

def re_api(api):
    # 使用正则表达式匹配目标字符串
    match = re.match(r'(/[^?]+)', api)

    if match:
        re_api = match.group(1)
        return re_api


def delete_old_file(file_path):
    """
    删除旧文件（兼容Django相对路径/绝对路径）
    :param file_path: 文件路径（user.avatar.path 或 URL相对路径）
    """
    if not file_path:
        return
    # 转换为绝对路径
    if not op.isabs(file_path):
        file_path = op.join(settings.MEDIA_ROOT, file_path)
    # 存在则删除
    if op.exists(file_path):
        try:
            os.remove(file_path)
            print(f"[成功] 删除旧文件：{file_path}")
        except Exception as e:
            print(f"[失败] 删除旧文件 {file_path} 出错：{str(e)}")


def process_image(image_file, target_height=TARGET_HEIGHT, max_size=MAX_FILE_SIZE):
    """
    图片标准化处理：
    1. 转换为JPG格式（处理透明通道）
    2. 按比例调整高度为1024
    3. 压缩质量至1M以内
    :param image_file: 上传的图片文件对象（InMemoryUploadedFile）
    :return: 处理后的InMemoryUploadedFile对象
    """
    try:
        # 打开图片并处理透明通道
        img = Image.open(image_file)
        if img.mode in ('RGBA', 'P', 'L'):  # 处理PNG透明/灰度图
            img = img.convert('RGB')

        # 按比例缩放（高度固定1024，宽度等比）
        width, height = img.size
        ratio = target_height / height
        new_width = int(width * ratio)
        img = img.resize((new_width, target_height),
                         Image.Resampling.LANCZOS)  # 高质量缩放（旧版本用Image.LANCZOS）

        # 动态压缩至1M以内
        img_byte_arr = io.BytesIO()
        quality = 95  # 初始质量
        while True:
            img_byte_arr.seek(0)
            img_byte_arr.truncate()  # 清空之前的内容
            img.save(img_byte_arr, format=TARGET_FORMAT, quality=quality, optimize=True)
            file_size = img_byte_arr.tell()
            # 满足大小或质量已到下限则停止
            if file_size <= max_size or quality <= 10:
                break
            quality -= 5  # 每次降低5%质量

        # 构建新的上传文件对象（强制后缀为jpg）
        new_file_name = f"{op.splitext(image_file.name)[0]}{TARGET_EXT}"
        processed_file = InMemoryUploadedFile(
            file=img_byte_arr,
            field_name=image_file.field_name,
            name=new_file_name,
            content_type=f'image/{TARGET_FORMAT.lower()}',
            size=file_size,
            charset=None
        )
        return processed_file
    except Exception as e:
        raise Exception(f"图片处理失败：{str(e)}")


def extract_zip_file(zip_file):
    """
    解压zip压缩包，返回 {身份证号: 图片文件对象} 映射
    :param zip_file: 上传的zip文件对象
    :return: dict
    """
    id_card_image_map = {}
    try:
        with zipfile.ZipFile(zip_file, 'r') as zf:
            for file_name in zf.namelist():
                # 过滤文件夹/非图片文件
                if file_name.endswith('/') or not file_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    continue
                # 提取身份证号（文件名去后缀）
                id_card = op.splitext(op.basename(file_name))[0].strip()
                if not id_card:  # 空身份证号跳过
                    continue
                # 读取文件内容并构建上传文件对象
                file_data = zf.read(file_name)
                file_obj = io.BytesIO(file_data)
                img_file = InMemoryUploadedFile(
                    file=file_obj,
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
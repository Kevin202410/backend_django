import re
import datetime
from typing import Tuple, Optional


class IDCardValidationError(Exception):
    """身份证号校验异常（自定义异常，便于业务层捕获）"""
    pass


def clean_id_card(id_card: str) -> str:
    """
    清理身份证号：去除所有空格 + 末尾X转大写
    :param id_card: 原始身份证号
    :return: 清理后的身份证号
    """
    if not isinstance(id_card, str):
        raise IDCardValidationError("身份证号必须为字符串类型")

    # 1. 去除所有空格（首尾、中间）
    cleaned_id_card = id_card.replace(" ", "")
    # 2. 转大写（处理末尾x/X）
    cleaned_id_card = cleaned_id_card.upper()
    return cleaned_id_card


def validate_id_card_format(id_card: str) -> bool:
    """
    校验身份证号格式：18位，前17位为数字，第18位为数字或X
    :param id_card: 清理后的身份证号
    :return: 格式合法返回True，否则抛异常
    """
    # 1. 校验长度
    if len(id_card) != 18:
        raise IDCardValidationError("身份证号长度必须为18位")

    # 2. 校验前17位为数字
    if not id_card[:17].isdigit():
        raise IDCardValidationError("身份证号前17位必须为数字")

    # 3. 校验第18位为数字或X
    if not (id_card[17].isdigit() or id_card[17] == "X"):
        raise IDCardValidationError("身份证号第18位必须为数字或大写X")

    return True


def validate_id_card_birthday(id_card: str) -> bool:
    """
    校验身份证号中的出生日期：合法日期 + 年龄合理（≤150岁）
    :param id_card: 清理后的身份证号
    :return: 出生日期合法返回True，否则抛异常
    """
    # 1. 提取出生日期（第7-14位）
    birthday_str = id_card[6:14]
    try:
        birthday = datetime.datetime.strptime(birthday_str, "%Y%m%d").date()
    except ValueError:
        raise IDCardValidationError(f"身份证号中出生日期{birthday_str}格式非法（需为YYYYMMDD）")

    # 2. 校验出生日期合理性（不早于150年前，不晚于当前日期）
    today = datetime.date.today()
    max_birth_year = today.year - 150
    if birthday.year < max_birth_year:
        raise IDCardValidationError(f"身份证号出生日期{birthday_str}不合理（年龄超过150岁）")
    if birthday > today:
        raise IDCardValidationError(f"身份证号出生日期{birthday_str}不合理（晚于当前日期）")

    return True


def calculate_id_card_check_digit(id_card_prefix: str) -> str:
    """
    计算身份证号校验位（根据前17位）
    :param id_card_prefix: 身份证号前17位（数字）
    :return: 计算出的校验位（数字或X）
    """
    # 1. 加权因子（国标规则）
    weight_factors = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    # 2. 校验码映射（国标规则）
    check_code_map = {0: "1", 1: "0", 2: "X", 3: "9", 4: "8", 5: "7", 6: "6", 7: "5", 8: "4", 9: "3", 10: "2"}

    # 3. 计算加权和
    total = sum([int(id_card_prefix[i]) * weight_factors[i] for i in range(17)])
    # 4. 计算模11的结果
    mod = total % 11
    # 5. 映射校验位
    return check_code_map[mod]


def validate_id_card_check_digit(id_card: str) -> bool:
    """
    校验身份证号校验位（第18位）是否合法
    :param id_card: 清理后的身份证号
    :return: 校验位合法返回True，否则抛异常
    """
    # 1. 提取前17位和实际校验位
    id_card_prefix = id_card[:17]
    actual_check_digit = id_card[17]
    # 2. 计算期望校验位
    expected_check_digit = calculate_id_card_check_digit(id_card_prefix)
    # 3. 比对校验位
    if actual_check_digit != expected_check_digit:
        raise IDCardValidationError(
            f"身份证号校验位非法：实际为{actual_check_digit}，期望为{expected_check_digit}"
        )
    return True


def validate_id_card(id_card: str) -> Tuple[bool, Optional[str]]:
    """
    身份证号全量校验（整合所有规则）
    :param id_card: 原始身份证号
    :return: (校验结果, 错误信息) → 合法：(True, None)，非法：(False, 错误信息)
    """
    try:
        # 步骤1：清理身份证号（去空格、X大写）
        cleaned_id = clean_id_card(id_card)
        # 步骤2：格式校验
        validate_id_card_format(cleaned_id)
        # 步骤3：出生日期校验
        validate_id_card_birthday(cleaned_id)
        # 步骤4：校验位校验
        validate_id_card_check_digit(cleaned_id)
        return True, None
    except IDCardValidationError as e:
        return False, str(e)
    except Exception as e:
        return False, f"身份证号校验异常：{str(e)}"
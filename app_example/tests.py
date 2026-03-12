import threading

from django.test import TestCase

# Create your tests here.
import time
from utils.common import bas64_decode_text, bas64_encode_text


if __name__ == '__main__':
    text = "shenyy"
    text1 = bas64_encode_text(text)
    text2 = bas64_decode_text(text1)
    print("加密后：", text1, "\n解密后：",  text2  )

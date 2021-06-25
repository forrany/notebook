# coding: utf-8
"""Notebook related constants"""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import os

AUTH_API_ROOT = "http://{host}:{port}/v3/auth".format(
    host=os.environ.get("AUTH_API_HOST"), port=os.environ.get("AUTH_API_PORT")
)
DATALAB_API_ROOT = "http://{host}:{port}/v3/datalab".format(
    host=os.environ.get("DATALAB_API_HOST"), port=os.environ.get("DATALAB_API_PORT")
)
DATAFLOW_API_ROOT = "http://{host}:{port}/v3/dataflow".format(
    host=os.environ.get("DATAFLOW_API_HOST"), port=os.environ.get("DATAFLOW_API_PORT")
)

# http请求正常状态码
HTTP_STATUS_OK = 200

DELIMITER = "##"
DELETE_TAG = "deleted"

CODE_PREFIX = "1580"
SUCCESS_CODE = "{}{}".format(CODE_PREFIX, "200")
GIT_COMMAND_CODE = "{}{}".format(CODE_PREFIX, "011")
SPECIAL_CHAR_CODE = "{}{}".format(CODE_PREFIX, "012")
VERSION_EXIST_CODE = "{}{}".format(CODE_PREFIX, "013")
VERSION_NULL_CODE = "{}{}".format(CODE_PREFIX, "014")
BK_USERNAME_NULL_CODE = "{}{}".format(CODE_PREFIX, "015")
AUTH_INSUFFICIENT_CODE = "{}{}".format(CODE_PREFIX, "016")
INTERNAL_INTERFACE_CODE = "{}{}".format(CODE_PREFIX, "017")

# 返回信息描述
RESPONSE_MESSAGE = {
    SUCCESS_CODE: "ok",
    GIT_COMMAND_CODE: "git操作失败",
    SPECIAL_CHAR_CODE: "版本号不能包含特殊字符%s" % DELIMITER,
    VERSION_EXIST_CODE: "版本号已存在，请重新输入",
    VERSION_NULL_CODE: "版本号不能为空",
    BK_USERNAME_NULL_CODE: "缺少用户信息",
    AUTH_INSUFFICIENT_CODE: "权限不足，项目观察员不能执行和保存笔记，只能查看笔记内容",
    INTERNAL_INTERFACE_CODE: "依赖接口异常",
}

EXAMPLE_NB = "example.ipynb"
EXAMPLE_EN_NB = "example_en.ipynb"
MLSQL_NB = "mlsql.ipynb"

RUNNING = "running"
MLSQL_ERR_CODE = "1586015"

# 终止mlsql重试次数
STOP_MODELING_TIMES = 4

# 终止mlsql等待的时间间隔
STOP_MODELING_WAIT_TIME = 3

# 获取mlsql终止状态等待的时间间隔
GET_STOP_STATUS_WAIT_TIME = 1

# 如果返回内容中包含以下信息，禁止展示给用户
FORBIDDEN_DATA = [
    os.environ.get(host)
    for host in [
        "AUTH_API_HOST",
        "META_API_HOST",
        "QUERYENGINE_API_HOST",
        "DATALAB_API_HOST",
        "DATAFLOW_API_HOST",
        "DATAHUB_API_HOST",
        "GIT_HOST",
    ]
]

# 如果代码中包含以下信息，禁止执行
FORBIDDEN_CODES = [
    "/site-packages/command",
    "/site-packages/notebook",
    ".git",
    "import os",
    "from os import",
    "import subprocess",
    "from subprocess import",
]
FORBIDDEN_CODES.extend(FORBIDDEN_DATA)

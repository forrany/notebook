# coding: utf-8
"""Pizza related api"""

# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import json
import requests

from notebook.services.constants import (
    DATAFLOW_API_ROOT,
    DATALAB_API_ROOT,
    HTTP_STATUS_OK,
    AUTH_API_ROOT,
    SUCCESS_CODE,
    AUTH_INSUFFICIENT_CODE,
    INTERNAL_INTERFACE_CODE,
)


def check_project_auth(project_id, bk_username):
    """
    校验用户是否有数据开发的权限，如果无此权限，表明用户是项目观察员，没有对笔记进行保存的权限
    """
    response = requests.post(
        url="%s/users/%s/check/" % (AUTH_API_ROOT, bk_username),
        headers={
            "Content-Type": "application/json; charset=utf-8",
        },
        data=json.dumps({
            "action_id": "project.manage_flow",
            "object_id": project_id
        })
    )
    status, code = (
        (True, SUCCESS_CODE)
        if response.status_code == HTTP_STATUS_OK and response.json()["data"]
        else (False, AUTH_INSUFFICIENT_CODE)
        if response.status_code == HTTP_STATUS_OK
        else (False, INTERNAL_INTERFACE_CODE)
    )
    return status, code


def get_mlsql_info(kernel_id):
    """
    获取mlsql详情

    :param kernel_id: 内核id
    :return: 结果
    """
    url = "%s/notebooks/mlsql_info/?kernel_id=%s" % (DATALAB_API_ROOT, kernel_id)
    res = requests.get(url=url)
    return extract_response_result(res, "获取MLSQL详情失败")


def get_mlsql_task_info(notebook_id):
    """
    获取mlsql任务详情

    :param notebook_id: 笔记id
    :return: 结果
    """
    url = "%s/flow/modeling/get_task_id/?notebook_id=%s" % (DATAFLOW_API_ROOT, notebook_id)
    res = requests.get(url=url)
    return extract_response_result(res, "获取MLSQL任务详情失败")


def stop_modeling(task_id):
    """
    终止mlsql任务

    :param task_id: mlsql任务id
    :return: 结果
    """
    url = "%s/flow/modeling/stop_modeling/" % DATAFLOW_API_ROOT
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = json.dumps({"task_id": task_id})
    res = requests.post(url=url, headers=headers, data=data)
    return extract_response_result(res, "终止MLSQL任务失败")


def get_mlsql_status(task_id):
    """
    获取mlsql执行状态

    :param task_id: 任务id
    :return: 结果
    """
    url = "%s/flow/modeling/sync_status/?task_id=%s" % (DATAFLOW_API_ROOT, task_id)
    res = requests.get(url=url)
    return extract_response_result(res, "获取MLSQL执行状态失败")


def extract_response_result(res, error_message):
    """
    处理接口返回结果

    :param res: 返回内容
    :param error_message: 异常信息
    :return: 结果
    """
    status, result = (
        (True, res.json()) if res.status_code == HTTP_STATUS_OK else (False, "%s: %s" % (error_message, res.content))
    )
    return status, result


def generate_response(result, message, code, errors, data=None):
    """
    生成返回内容

    :param result: 结果
    :param message: 异常信息
    :param code: 状态码
    :param errors: 异常详情
    :param data: 数据
    :return: 返回内容
    """
    return json.dumps({"result": result, "message": message, "code": code, "errors": errors, "data": data})

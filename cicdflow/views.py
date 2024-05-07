import time

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
# from rest_framework.generics import GenericAPIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from typing import Any
import traceback

from cicdflow.models import JiraIssue
from cicdflow.serializers import JiraIssueSerializer
from utils.jira_webhook_api import JiraEventWebhookAPI
import logging
# c_logger = logging.getLogger("console_logger")
d_logger = logging.getLogger("default_logger")


class TestView(APIView):
    def get(
            self,
            request,
            *args: Any,
            **kwargs: Any
    ) -> Response:
        try:
            time.sleep(30)
            return Response(status=status.HTTP_200_OK)
        except Exception:
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Jira 升级自动化流程
class JiraFlowView(APIView):
    """
    webhook 触发条件:
        project = UPGRADE AND issuetype = 升级 AND status in ("SQL PENDING", "SQL PROCESSING","CONFIG PROCESSING", "CODE PROCESSING","FIX PENDING")
        project = UPGRADE AND issuetype = 升级
    webhook 事件类型:
        jira:issue_created = issue 创建事件，初始化升级数据，开始升级流程。
        jira:issue_updated = issue 更新事件，更新升级数据，已 webhook 中数据执行对应处理逻辑。
            REVIEW PENDING: xxx
            SQL PENDING: 判断是否存在 SQL，存在则提交到 Archery。
            SQL PROCESSING: 判断是否存在待执行 SQL，存在则触发 Archery API 自动执行。
            CONFIG PROCESSING: 由运维人员人工触发进入下一步。
            CODE PROCESSING: 判断是否有代码升级，存在则升级应用。
            FIX PENDING: 升级过程出现异常则跳转到该状态，等待人工修复。
    """
    @swagger_auto_schema(
        operation_summary="Jira Webhook API",
        operation_description="处理 Jira webhook 请求，根据状态做对应流程处理",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "issue": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="Jira Issue 信息",
                    properties={
                        "fields": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            description="Issue 所有字段内容",
                            properties={
                                "summary": openapi.Schema(type=openapi.TYPE_STRING, description="Issue 标题"),
                                "status": openapi.Schema(type=openapi.TYPE_STRING, description="Issue 状态信息"),
                                "environment": openapi.Schema(type=openapi.TYPE_STRING, description="升级环境"),
                                "customfield_11113": openapi.Schema(type=openapi.TYPE_STRING, description="项目名称"),
                                "customfield_11100": openapi.Schema(type=openapi.TYPE_STRING, description="功能列表"),
                                "customfield_11104": openapi.Schema(type=openapi.TYPE_STRING, description="升级类型"),
                                "customfield_11106": openapi.Schema(type=openapi.TYPE_STRING, description="升级是否维护"),
                                "customfield_11108": openapi.Schema(type=openapi.TYPE_STRING, description="SQL 升级内容"),
                                "customfield_11109": openapi.Schema(type=openapi.TYPE_STRING, description="Nacos 升级内容"),
                                "customfield_11110": openapi.Schema(type=openapi.TYPE_STRING, description="Config 升级内容"),
                                "customfield_11112": openapi.Schema(type=openapi.TYPE_STRING, description="Code 升级内容")
                            }
                        ),
                        "id": openapi.Schema(type=openapi.TYPE_STRING, description="issue_id"),
                        "key": openapi.Schema(type=openapi.TYPE_STRING, description="issue_key"),
                        "self": openapi.Schema(type=openapi.TYPE_STRING, description="Issue URL")
                    }
                ),
                "issue_event_type_name": openapi.Schema(type=openapi.TYPE_STRING, description="Issue 事件类型名称"),
                "timestamp": openapi.Schema(type=openapi.TYPE_INTEGER, description="时间戳"),
                "user": openapi.Schema(type=openapi.TYPE_OBJECT, description="用户信息"),
                "webhookEvent": openapi.Schema(type=openapi.TYPE_STRING, description="Jira issue event 类型")
            }
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "status": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="返回处理结果"),
                    "msg": openapi.Schema(type=openapi.TYPE_STRING, description="返回消息"),
                    "data": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        description="返回数据",
                        properties={}
                    )
                }
            )
        }
    )
    def post(
            self,
            request,
            *args: Any,
            **kwargs: Any
    ) -> Response:
        return_data = {
            "status": False,
            "msg": "",
            "data": {}
        }
        try:
            # 获取 Jira webhook http request data 转换自定义 JiraEventWebhookAPI 对象
            jira_event_webhook_obj = JiraEventWebhookAPI(request.data)

            # 获取 JiraEventWebhookAPI 序列化对象中的数据
            if jira_event_webhook_obj.webhook_environment == 'PROD':
                raise Exception('运营环境工单跳过，不处理 webhook 请求')
            webhook_event = jira_event_webhook_obj.webhook_event
            webhook_data = jira_event_webhook_obj.webhook_data
            issue_key = webhook_data.get("issue_key")
            issue_status = webhook_data.get("issue_status")
            summary = webhook_data.get("summary")

            # webhook 事件为 created 时，写入工单数据到数据库，开始完整升级流程
            if webhook_event == "jira:issue_created":
                # 根据 JiraIssue 序列化器序列化当前 Jira webhook 数据
                jira_issue_ser = JiraIssueSerializer(data=jira_event_webhook_obj.webhook_data)
                jira_issue_ser.is_valid(raise_exception=True)
                jira_issue_ser_data = dict(jira_issue_ser.validated_data)
                # Jira 工单数据存入数据库
                jira_issue_ser.save()
                d_logger.info(f"新建 Jira 工单 {summary} 成功，写入工单数据到数据库中。")
                webhook_result = jira_event_webhook_obj.created_event_action(
                    current_issue_data=jira_issue_ser_data,
                )

            # webhook 事件为 updated 时，根据当前 issue 状态执行对应函数逻辑
            elif webhook_event == "jira:issue_updated":
                # 获取之前 JiraIssue 表中的工单数据，获取前先确保数据库中存在 issue 数据
                last_issue_obj = JiraIssue.objects.get(issue_key=issue_key)

                # 根据 JiraIssue 序列化器序列化当前 Jira webhook 数据
                jira_issue_ser = JiraIssueSerializer(instance=last_issue_obj, data=webhook_data)
                jira_issue_ser.is_valid(raise_exception=True)
                jira_issue_ser_data = dict(jira_issue_ser.validated_data)

                # 判断当前 issue 状态，根据状态获取数据进行变更。每次转换状态前更新当前 issue_obj issue_status 字段
                match issue_status:
                    # SQL PENDING 状态
                    case "SQL PENDING":
                        webhook_result = jira_event_webhook_obj.updated_event_sql_pending(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jira_issue_ser_data,
                        )
                    # SQL PROCESSING 状态
                    case "SQL PROCESSING":
                        webhook_result = jira_event_webhook_obj.updated_event_sql_processing(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jira_issue_ser_data
                        )
                    # CONFIG PROCESSING 状态
                    case "CONFIG PROCESSING":
                        webhook_result = jira_event_webhook_obj.updated_event_config_processing(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jira_issue_ser_data
                        )
                    # CODE PROCESSING 状态
                    case "CODE PROCESSING":
                        webhook_result = jira_event_webhook_obj.updated_event_code_processing(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jira_issue_ser_data
                        )
                    # FIX PENDING 状态，此状态为等待人工修复不做状态转换
                    case "FIX PENDING":
                        webhook_result = jira_event_webhook_obj.updated_event_fix_pending(
                            last_issue_obj=last_issue_obj
                        )
                    case _:
                        webhook_result = {
                            "status": True,
                            "msg": f"工单：{summary} 当前 issue 状态为 <{issue_status}>，无需操作触发下一步流程，忽略状态转换",
                            "data": dict()
                        }
            else:
                raise KeyError("webhook event 事件不为 jira:issue_created 或 jira:issue_updated")

            # webhook 处理结果非 true 时，返回错误信息
            if not webhook_result["status"]:
                return_data["msg"] = f"Jira 状态 <{issue_status}> webhook 调用 jira_webhook_api 失败，返回消息 --> {webhook_result['msg']}"
                return_data["data"] = webhook_result["data"]
                d_logger.error(return_data)
                return Response(data=return_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # webhook 正常触发，记录返回日志
            return_data["status"] = True
            return_data["msg"] = f"Jira 状态 <{issue_status}> webhook 触发成功。调用 jira_webhook_api 返回原始消息 --> {webhook_result['msg']}"
            return_data["data"] = webhook_result["data"]
            d_logger.info(return_data)
            return Response(data=return_data, status=status.HTTP_200_OK)
        except JiraIssue.DoesNotExist as err:
            return_data["msg"] = f"Jira webhook 触发失败，当前工单不存在数据库中。异常原因：{err}"
            d_logger.error(return_data)
            return Response(data=return_data, status=status.HTTP_404_NOT_FOUND)
        except KeyError as err:
            return_data["msg"] = f"Jira webhook 触发失败，异常原因：{err}"
            d_logger.error(return_data)
            return Response(data=return_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception:
            return_data["msg"] = f"Jira webhook 触发失败，异常原因：{traceback.format_exc()}"
            d_logger.error(return_data)
            return Response(data=return_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

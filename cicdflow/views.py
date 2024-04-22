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


# Jira 升级自动化流程
class JiraFlowView(APIView):
    """
    webhook 触发条件:
        project = UPGRADE AND issuetype = 升级 AND status in ("REVIEW PENDING", "SQL PENDING", "SQL PROCESSING","CONFIG PROCESSING", "CODE PROCESSING","FIX PENDING")
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
        operation_description="接收 Jira webhook 请求，根据状态做对应处理",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={}
        ),
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "status": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "msg": openapi.Schema(type=openapi.TYPE_STRING, description="返回消息"),
                    "data": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={},
                        description="返回数据"),
                }
            ),
            500: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "status": openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    "msg": openapi.Schema(type=openapi.TYPE_STRING, description="返回消息"),
                    "data": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={},
                        description="返回数据"),
                }
            )
        }
    )
    def post(self,
             request,
             *args: Any,
             **kwargs: Any) -> Response:
        return_data = {
            "status": False,
            "msg": "",
            "data": {}
        }
        try:
            # 获取 Jira webhook http request data 转换自定义 JiraEventWebhookAPI 对象
            jira_event_webhook_obj = JiraEventWebhookAPI(request.data)

            # 获取 JiraEventWebhookAPI 序列化对象中的数据
            webhook_environment = jira_event_webhook_obj.webhook_environment
            webhook_event = jira_event_webhook_obj.webhook_event
            webhook_data = jira_event_webhook_obj.webhook_data
            issue_key = webhook_data.get("issue_key")
            issue_status = webhook_data.get("issue_status")
            summary = webhook_data.get("summary")
            d_logger.info(webhook_data)
            d_logger.info(webhook_event)

            # 暂时不处理运营环境 webhook
            if webhook_environment == "PROD":
                raise Exception("运营环境跳过，不处理 webhook!!!!!!!!")

            # webhook 事件为 created 时，写入工单数据到数据库，开始完整升级流程
            if webhook_event == "jira:issue_created":
                # 根据 JiraIssue 序列化器序列化当前 Jira webhook 数据
                jira_issue_ser = JiraIssueSerializer(data=jira_event_webhook_obj.webhook_data)
                jira_issue_ser.is_valid(raise_exception=True)
                jira_issue_ser_data = dict(jira_issue_ser.validated_data)
                # Jira 工单数据存入数据库
                jira_issue_ser.save()
                d_logger.info("新建 Jira 工单成功，写入工单数据到数据库中。")
                webhook_result = jira_event_webhook_obj.created_event_action(
                    current_issue_data=jira_issue_ser_data,
                )

            # webhook 事件为 updated 时，根据当前 issue 状态执行对应函数逻辑
            elif webhook_event == "jira:issue_updated":
                # 获取之前 JiraIssue 表中的工单数据，获取前先确保数据库中存在 issue 数据
                assert JiraIssue.objects.filter(issue_key=issue_key), "当前 Jira Issue 不存在数据库中，中止继续执行"
                last_issue_obj = JiraIssue.objects.get(issue_key=issue_key)

                # 根据 JiraIssue 序列化器序列化当前 Jira webhook 数据
                jira_issue_ser = JiraIssueSerializer(instance=last_issue_obj, data=webhook_data)
                jira_issue_ser.is_valid(raise_exception=True)
                jira_issue_ser_data = dict(jira_issue_ser.validated_data)

                # 判断当前 issue 状态，根据状态获取数据进行变更。每次转换状态前更新当前 issue DB 数据
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
                        msg = f"工单：{summary} 当前 issue 状态为 <{issue_status}>，不需要触发下一步流程，不更新 issue 数据，忽略状态转换"
                        webhook_result = {"status": True, "msg": msg}
            else:
                raise KeyError("jira webhook event 事件不为 created 或 updated，请检查 webhook event 类型")

            # webhook 处理结果非 true 时，返回错误信息
            if not webhook_result["status"]:
                return_data["msg"] = f"webhook 触发成功，执行触发状态逻辑返回错误."
                return_data["data"] = webhook_result
                d_logger.error(return_data)
                return Response(data=return_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # webhook 正常触发，记录返回日志
            return_data["status"] = True
            return_data["msg"] = f"Jira 状态 {issue_status} webhook 触发成功."
            return_data["data"] = webhook_result
            d_logger.info(return_data)
            return Response(data=return_data, status=status.HTTP_200_OK)
        except KeyError as err:
            return_data["msg"] = f"webhook 触发失败，issue 非 created 或 updated 操作，异常原因：{err.__str__()}"
            d_logger.error(return_data)
            return Response(data=return_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception:
            return_data["msg"] = f"webhook 触发失败，异常原因：{traceback.format_exc()}"
            d_logger.error(return_data)
            return Response(data=return_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

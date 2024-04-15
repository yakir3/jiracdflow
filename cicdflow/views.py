from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
# from rest_framework.generics import GenericAPIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from time import sleep
from typing import Any
import traceback

from cicdflow.models import JiraIssue, SqlWorkflow
from cicdflow.serializers import JiraIssueSerializer, SqlWorkflowSerializer
from utils.cicdflow_util import JiraEventWebhookAPI, JiraAPI
import logging
# c_logger = logging.getLogger('console_logger')
d_logger = logging.getLogger('default_logger')


# Jira 升级自动化流程
class JiraFlowView(APIView):
    """
    WebHook 触发条件:
        project = UPGRADE AND issuetype = 升级 AND status in ("SQL PENDING", "SQL PROCESSING","CONFIG PROCESSING", "CODE PROCESSING","FIX PENDING")
    WebHook 事件类型:
        jira:issue_created = issue 创建事件，初始化升级数据，开始升级流程。
        jira:issue_updated = issue 更新事件，更新升级数据，已 WebHook 中数据执行对应处理逻辑。
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
                    'status': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'msg': openapi.Schema(type=openapi.TYPE_STRING, description='返回消息'),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={},
                        description='返回数据'),
                }
            ),
            500: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'msg': openapi.Schema(type=openapi.TYPE_STRING, description='返回消息'),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={},
                        description='返回数据'),
                }
            )
        }
    )
    def post(self,
             request,
             *args: Any,
             **kwargs: Any) -> Response:
        return_data = {
            'status': False,
            'msg': '',
            'data': {}
        }
        try:
            d_logger.info(request.data)
            return Response(data=return_data, status=status.HTTP_200_OK)

            # 初始化并序列化 webhook http request data 数据
            jira_event_webhook_obj = JiraEventWebhookAPI(request.data)
            webhook_env = jira_event_webhook_obj.webhook_env
            webhook_event = jira_event_webhook_obj.webhook_event

            # 暂时不处理运营环境 webhook
            if webhook_env == 'PROD':
                raise Exception('运营环境跳过，不处理 webhook!!!!!!!!')

            # webhook 事件为 created 时，调用 created_event_operate 方法初始化工单与开始流程
            if webhook_event == 'jira:issue_created':
                # jiraissue_ser = JiraIssueSerializer(data=jira_event_webhook_obj.webhook_data)
                # jiraissue_ser.is_valid(raise_exception=True)
                # webhook_result = jira_event_webhook_obj.created_event_operate(
                #     current_issue_data=dict(jiraissue_ser.validated_data),
                #     serializer=jiraissue_ser
                # )
                d_logger.info('工单被创建.....')

            # webhook 事件为 updated 时，判断当前 issue 状态，根据状态进行转换
            elif webhook_event == 'jira:issue_updated':
                # 获取当前 Jira webhook 表单中数据
                current_webhook_data = jira_event_webhook_obj.webhook_data
                current_issue_key = current_webhook_data.get('issue_key')
                current_status = current_webhook_data.get('status')
                current_summary = current_webhook_data.get('summary')
                # 获取 JiraIssue 表中的数据
                last_issue_obj = JiraIssue.objects.get(issue_key=current_issue_key)
                # 根据 JiraIssue 序列化器序列化当前 webhook 数据
                jiraissue_ser = JiraIssueSerializer(instance=last_issue_obj, data=current_webhook_data)
                jiraissue_ser.is_valid(raise_exception=True)
                # 根据升级工单名获取 SqlWorkflow 表数据
                # sql_workflow_obj = SqlWorkflow.objects.filter(workflow_name=current_summary)

                # 判断当前 webhook 状态，根据状态获取数据进行变更。每次转换状态前更新当前 issue DB 数据
                jiraissue_ser_data = dict(jiraissue_ser.validated_data)
                match current_status:
                    # SQL PENDING 状态，可转变状态：无SQL升级/已升级 ｜ 提交SQL
                    case 'SQL PENDING':
                        webhook_result = jira_event_webhook_obj.updated_event_sql_pending(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jiraissue_ser_data,
                            sqlworkflow_ser=SqlWorkflowSerializer,
                            sql_workflow_ins=SqlWorkflow
                        )
                    # SQL执行中状态
                    case 'SQL PROCESSING':
                        webhook_result = jira_event_webhook_obj.updated_event_sql_processing(
                            last_issue_obj=last_issue_obj,
                            sql_workflow_ins=SqlWorkflow,
                            current_issue_data=jiraissue_ser_data
                        )
                    # 配置文件处理中状态
                    case 'CONFIG PROCESSING':
                        webhook_result = jira_event_webhook_obj.updated_event_config_processing(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jiraissue_ser_data
                        )
                    # 升级代码中状态
                    case 'CODE PROCESSING':
                        webhook_result = jira_event_webhook_obj.updated_event_code_processing(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jiraissue_ser_data
                        )
                    # 升级过程异常，待人工修复状态
                    case 'FIX PENDING':
                        webhook_result = jira_event_webhook_obj.updated_event_fix_pending(
                            current_issue_key=current_issue_key
                        )
                    case _:
                        msg = f"工单：{current_summary} 当前 issue 状态为 <{current_status}>，不需要触发下一步流程，不更新 issue 数据，忽略状态转换"
                        webhook_result = {'status': True, 'msg': msg}
            else:
                raise KeyError('jira webhook event 事件不为 created 或 updated，请检查 webhook event 类型')
            return_data['data'] = webhook_result

            # webhook 处理结果非 true 时，返回错误信息
            if not webhook_result['status']:
                return_data['msg'] = 'WebHook 触发执行相应状态返回错误结果.'
                d_logger.error(webhook_result)
                return Response(data=return_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            # webhook 正常触发，记录返回日志
            return_data['status'] = True
            return_data['msg'] = 'WebHook 触发成功，执行相应状态返回正确结果.'
            return_data['data'] = webhook_result
            d_logger.info(return_data)
            return Response(data=return_data, status=status.HTTP_200_OK)
        except KeyError as err:
            return_data['msg'] = f'WebHook 数据中没有 created 或 updated 操作,异常原因：{err.__str__()}'
            d_logger.error(return_data)
            return Response(data=return_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as err:
            tb_str = traceback.format_exc()
            # return_data['msg'] = f'webhook 触发失败，异常原因：{err.__str__()}'
            return_data['msg'] = f'webhook 触发失败，异常原因：{tb_str}'
            d_logger.error(return_data)
            return Response(data=return_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

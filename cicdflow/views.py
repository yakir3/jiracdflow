from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
# from rest_framework.generics import GenericAPIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from time import sleep
from typing import Any

from cicdflow.models import JiraWorkflow, SqlWorkflow
from cicdflow.serializers import JiraWorkflowSerializer, CICDFlowSerializer, SqlWorkflowSerializer
from util.cicdflow_util import JiraEventWebhookAPI, JiraAPI
import logging
# c_logger = logging.getLogger('console_logger')
d_logger = logging.getLogger('default_logger')


# 接收自动发包系统请求，创建或迭代更新 Jira 升级工单
class CICDFlowView(APIView):
    @swagger_auto_schema(
        operation_summary="查询升级状态",
        operation_description="工单名或 sql_id 查询升级状态",
        # request_body=openapi.Schema(
        #   type=openapi.TYPE_STRING,
        # ),
        manual_parameters=[
            openapi.Parameter('summary', openapi.IN_QUERY, description='升级工单名称', type=openapi.TYPE_STRING),
            openapi.Parameter('sql_id', openapi.IN_QUERY, description='单个 sql 文件唯一 id', type=openapi.TYPE_STRING, required=False)
        ],
        responses={
            200: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'code': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='接口返回代码'),
                    'msg': openapi.Schema(type=openapi.TYPE_STRING, description='返回消息'),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'summary': openapi.Schema(type=openapi.TYPE_STRING, description='升级工单名称'),
                            'upgrade_status': openapi.Schema(type=openapi.TYPE_INTEGER, description='升级工单状态代码'),
                            'sql_info': openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                description='SQL 升级信息',
                                items=openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        'sql_id': openapi.Schema(type=openapi.TYPE_STRING, description='sql_id, 唯一值'),
                                        'status': openapi.Schema(type=openapi.TYPE_STRING, description='单条 SQL 工单当前状态',)
                                    }
                                )
                            )
                        },
                        description='返回数据'),
                }
            ),
            400: 'Bad Request'
        }
    )
    def get(self, request, *args, **kwargs):
        return_data = {'code': 10200, 'msg': 'success', 'data': {}}
        try:
            summary = request.GET.get('summary')
            sql_id = request.GET.get('sql_id')
            assert summary, "参数必选项 summary 参数缺失，工单编号名称为必需值"

            # 根据查询参数，查询 jira_workflow、sql_workflow 表
            jira_obj = JiraWorkflow.objects.get(summary=summary)

            # 查询返回的 sql_info 数据
            upgrade_status_map = {
                'UAT升级完成': 100,
                'SQL待执行': 101,
                'SQL执行中': 102,
                'SQL执行失败': 150
            }
            sql_info_data = {
                'summary': jira_obj.summary,
                'upgrade_status': upgrade_status_map.get(jira_obj.status, jira_obj.status),
                'sql_info': list()
            }
            # 存在 sql_id 查询参数时，只返回具体某个 sql 文件的执行结果
            if sql_id:
                sql_workflow_obj = SqlWorkflow.objects.get(sql_id=sql_id)
                tmp_dict = dict()
                tmp_dict['sql_id'] = sql_id
                tmp_dict['status'] = sql_workflow_obj.w_status
                tmp_dict['errormessage'] = ''
                sql_info_data['sql_info'].append(tmp_dict)
            else:
                sql_workflow_obj = SqlWorkflow.objects.filter(workflow_name=summary)
                # sql_index 与 workflow_name 相同时，取 sql_release_info 版本较大的值返回
                from util.cicdflow_util import filtered_queryset
                from util.archery_api import ArcheryAPI
                filter_sql_workflow_list = filtered_queryset(sql_workflow_obj)
                archery_obj = ArcheryAPI()

                for sql_item in filter_sql_workflow_list:
                    w_id = sql_item.get('w_id')
                    sql_id = sql_item.get('sql_id')
                    w_status = sql_item.get('w_status')
                    # sql_info 工单存在 exception 状态时，从 archery_api 接口获取 errormessage
                    if w_status == 'workflow_exception':
                        select_result = archery_obj.get_workflows(args={'id': w_id})
                        errormessage = select_result['data'][0]['execute_result'][0]['errormessage']
                    else:
                        errormessage = ''
                    # 循环写入所有 sql 工单信息到 sql_info 列表中
                    tmp_dict = dict()
                    tmp_dict['sql_id'] = sql_id
                    tmp_dict['status'] = w_status
                    tmp_dict['errormessage'] = errormessage
                    sql_info_data['sql_info'].append(tmp_dict)

            return_data['data'] = sql_info_data
        except AssertionError as err:
            return_data['code'] = 10500
            return_data['msg'] = 'failed'
            return_data['data'] = {"error": f"{err.__str__()}"}
        except (JiraWorkflow.DoesNotExist, SqlWorkflow.DoesNotExist) as err:
            return_data['code'] = 10404
            return_data['msg'] = 'failed'
            return_data['data'] = {"error": f"工单名或 sql_id 查询数据不存在，错误内容：{err.__str__()}"}
        except Exception as err:
            return_data['code'] = 10500
            return_data['msg'] = 'failed'
            return_data['data'] = {"error": f"接口异常，异常原因： {err.__str__()}"}
        return Response(data=return_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_summary="触发Jira升级工单流程",
        operation_description="",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'project': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='项目：AC | QC',
                    default='AC'
                ),
                'summary': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='升级标题，不同升级标题需要为唯一值不要重复',
                    default='【XX】【升级】20230101_01'
                ),
                'issue_type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Jira工单类型',
                    default='升级'
                ),
                'env': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='升级环境',
                    default='UAT'
                ),
                'function_list': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING),
                    description='功能列表',
                    default=["【XXX】数据导出xxxx", "【XXX】报表中心数据优化"]
                ),
                'upgrade_type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='升级类型',
                    default='日常排版需求'
                ),
                'sql_info': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'svn_path': openapi.Schema(type=openapi.TYPE_STRING, description='svn路径',
                                                       default='database_xxx/xxx'),
                            'svn_file': openapi.Schema(type=openapi.TYPE_STRING, description='svn文件名',
                                                       default='05.act_ddl_xxx.sql'),
                            'svn_version': openapi.Schema(type=openapi.TYPE_STRING, description='svn版本',
                                                          default='999')
                        }
                    ),
                    description='SQL升级信息',
                    default=list()
                ),
                'apollo_info': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={}
                    ),
                    description='Apollo升级信息',
                    default=list()
                ),
                'config_info': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={}
                    ),
                    description='过滤文件升级信息',
                    default=list()
                ),
                'code_info': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'svn_path': openapi.Schema(type=openapi.TYPE_STRING, description='svn路径',
                                                       default='a18/cc_merchant_console'),
                            'svn_version': openapi.Schema(type=openapi.TYPE_STRING, description='svn版本',
                                                          default='1061'),
                            'tag': openapi.Schema(type=openapi.TYPE_STRING, description='是否v2 v3环境', default='')
                        }
                    ),
                    description='代码升级信息',
                    default=list()
                ),
            },
            required=['project', 'summary', 'env', 'sql_info', 'config_info', 'apollo_info', 'code_info']
        ),
        responses={
            201: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'status': openapi.Schema(type=openapi.TYPE_BOOLEAN,description='接口返回状态'),
                    'msg': openapi.Schema(type=openapi.TYPE_STRING, description='返回消息'),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={},
                        description='返回数据'),
                    'jira_issue_key': openapi.Schema(type=openapi.TYPE_STRING, description='jira 工单标识,status 为 True 时返回')
                }
            ),
            400: 'Bad Request'
        }
    )
    def post(self, request, *args, **kwargs):
        return_data = {'status': False, 'msg': '', 'data': request.data, 'jira_issue_key': ''}
        try:
            # 简单 token 认证
            authorization = request.headers.get('Authorization', None)
            token = "7e896f0d2bab499b9f7170aa3302d3b2"
            assert authorization == token
            # JIRA 实例，用于初始化创建 Jira 升级工单
            jira_obj = JiraAPI()

            # 调用 jira_api 创建或更新工单
            cicdflow_ser = CICDFlowSerializer(data=request.data)
            if cicdflow_ser.is_valid(raise_exception=True):
                # 获取序列化后的 request_data 数据
                cicdflow_ser_data = dict(cicdflow_ser.validated_data)

                # project 参数区分项目列表
                ac_project_list = [
                    'A22',
                    'QC',
                    'A18',
                    'A19',
                    'RS8',
                    'B01',
                ]
                current_project = cicdflow_ser_data['project']
                if current_project in ac_project_list:
                    cicdflow_ser_data['project'] = 'AC' if current_project != 'QC' else current_project
                else:
                    return_data['msg'] = f"Jira 不存在项目 {current_project}，无法创建或更新工单"
                    return Response(data=return_data, status=status.HTTP_404_NOT_FOUND)

                # 使用升级标题（唯一值）查询数据库是否已存在升级工单
                current_summary = cicdflow_ser_data.get('summary')
                jira_issue_obj_exists = JiraWorkflow.objects.filter(summary=current_summary)
                # 工单标题已存在，更新 Jira 工单并转换状态到 <UAT自动迭代升级> 进行迭代升级
                if jira_issue_obj_exists:
                    jira_issue_obj = jira_issue_obj_exists.get()
                    issue_key = jira_issue_obj.issue_key
                    issue_status = jira_issue_obj.status
                    # 判断 issue 状态是否为 <SQL待执行> 或 <UAT升级完成>，非此状态抛出异常，不允许更新 issue 数据
                    if issue_status == 'UAT升级完成':
                        d_logger.debug(f"工单：{current_summary} 状态为 <UAT升级完成>，正常流转流程")
                        trans_result = jira_obj.change_transition(issue_key, 'UAT自动迭代升级')
                        if not trans_result['status']:
                            return_data['msg'] = f"已存在 Jira 工单，转换工单状态失败，错误原因：{trans_result['data']}"
                            d_logger.warning(return_data)
                        # 从 <UAT升级完成> 状态变更，开始迭代升级
                        else:
                            return_data['status'] = True
                            return_data['msg'] = '已存在 Jira 工单，转换工单状态到<UAT自动迭代升级>，开始完整迭代升级流程。'
                            return_data['jira_issue_key'] = issue_key
                            d_logger.info(return_data)
                    # SQL待执行 状态数据有变化时会自动触发 webhook，无需人为调用 change_transition 方法变更状态
                    elif issue_status == 'SQL待执行' or issue_status == 'SQL执行失败':
                        return_data['status'] = True
                        return_data['msg'] = f"工单：{current_summary} 状态为 <SQL待执行> 或 <SQL执行失败>，重新提交 SQL 触发完整升级流程"
                        return_data['jira_issue_key'] = issue_key
                        # # 无数据变化时，强制触发 jira 的状态变化
                        # try:
                        #     sleep(3)
                        #     jira_obj.change_transition(issue_key, '触发提交SQL')
                        # except Exception as err:
                        #     print(err.__str__())
                        d_logger.info(return_data)
                    # elif issue_status == '开发/运维修改':
                    #     return_data['status'] = True
                    #     return_data['msg'] = f"工单：{current_summary} 状态为 <开发/运维修改>，开始完整迭代升级流程"
                    #     return_data['jira_issue_key'] = issue_key
                    #     d_logger.info(return_data)
                    else:
                        return_data['msg'] = '当前工单 issue 状态非 <SQL待执行> 或 <UAT升级完成> 或 <开发/运维修改> ，不允许开始升级流程，检查当前工单状态'
                        d_logger.warning(return_data)
                        return Response(data=return_data, status=status.HTTP_200_OK)
                    # 更新 Jira 工单，失败时抛出异常
                    update_result = jira_obj.issue_update(args=cicdflow_ser_data, issue_id=issue_key)
                    if not update_result['status']:
                        return_data['status'] = False
                        # jira 更新异常返回 JIRAError 类，需要转换为字符串
                        return_data['msg'] = update_result['data'].text
                        d_logger.warning(return_data)
                    return Response(data=return_data, status=status.HTTP_200_OK)
                # 不存在工单，新建 Jira 工单触发 issue_updated 事件
                else:
                    create_result = jira_obj.issue_create(args=cicdflow_ser_data)
                    # 新建工单失败，返回错误信息
                    if not create_result['status']:
                        # jira 创建异常返回 JIRAError 类，需要转换为字符串
                        return_data['msg'] = create_result['data'].text
                        d_logger.warning(return_data)
                        return Response(data=return_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    jira_issue_key=create_result['data'].key
                    # jira_issue_obj = JiraWorkflow.objects.get(summary=current_summary)
                    return_data['status'] = True
                    return_data['msg'] = '首次发包升级创建 Jira 工单成功，开始自动升级流程。'
                    return_data['jira_issue_key'] = jira_issue_key
                    d_logger.info(return_data)
                    return Response(data=return_data, status=status.HTTP_201_CREATED)
            return_data['msg'] = f"升级数据合法性未通过或提交到Jira失败，需检查请求 body 内容. 错误信息：{cicdflow_ser.errors}"
            d_logger.error(return_data)
            return Response(data=return_data, status=status.HTTP_400_BAD_REQUEST)
        except AssertionError:
            return_data['status'] = False
            return_data['msg'] = '验证 token 失败，请检查是否正确携带 Authorization header'
            d_logger.error(return_data)
            return Response(data=return_data, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as err:
            return_data['status'] = False
            return_data['msg'] = f"升级工单新建或更新到 Jira 异常，异常原因：{err.__str__()}"
            d_logger.error(return_data)
            return Response(data=return_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Jira 升级自动化流程
class JiraFlowView(APIView):
    swagger_schema = None
    """
    webhook 条件：
        project = AC and issuetype in (升级) and status in (SQL待执行, SQL执行中, CONFIG执行中,CODE执行中,"开发/运维修改")
        project = QC and issuetype in (升级) and status in (SQL待执行, SQL执行中, CONFIG执行中,CODE执行中,"开发/运维修改")
    webhook 判断：
        webhookEvent = jira:issue_created  --> 首次创建 jira issue，初始化升级数据
        webhookEvent = jira:issue_updated  --> 迭代或重新提交升级，更新升级数据，已最新数据重跑升级流程
            SQL待执行：判断是否存在 SQL，存在则提交到 Archery 
            SQL执行中：由 DBA 人工触发进入下一步
            CONFIG执行中：由运维人员人工触发进入下一步
            CODE执行中：判断是否有代码升级
    """
    def post(self,
             request,
             *args: Any,
             **kwargs: Any) -> Response:
        try:
            # 初始化并序列化 webhook request data 数据
            jira_event_webhook_obj = JiraEventWebhookAPI(request.data)
            # 暂时不处理运营环境 webhook
            if jira_event_webhook_obj.webhook_env == 'PRO':
                raise Exception('运营环境跳过，不处理 webhook!!!!!!!!')

            # webhook 事件为 created 时，判断当前 issue 状态，根据状态进行转换
            if jira_event_webhook_obj.webhook_event == 'jira:issue_created':
                jiraworkflow_ser = JiraWorkflowSerializer(data=jira_event_webhook_obj.webhook_data)
                jiraworkflow_ser.is_valid(raise_exception=True)
                webhook_result = jira_event_webhook_obj.created_event_operate(
                    current_issue_data=dict(jiraworkflow_ser.validated_data),
                    serializer=jiraworkflow_ser
                )

            # webhook 事件为 updated 时，判断当前 issue 状态，根据状态进行转换
            elif jira_event_webhook_obj.webhook_event == 'jira:issue_updated':
                # 获取当前 Jira webhook 中数据
                current_webhook_data = jira_event_webhook_obj.webhook_data
                current_issue_key = current_webhook_data.get('issue_key')
                current_status = current_webhook_data.get('status')
                current_summary = current_webhook_data.get('summary')
                # 获取 JiraWorkflow 表中上一次数据
                last_issue_obj = JiraWorkflow.objects.get(issue_key=current_issue_key)
                # 根据 JiraWorkflow 序列化器序列化当前 webhook 数据
                jiraworkflow_ser = JiraWorkflowSerializer(instance=last_issue_obj, data=current_webhook_data)
                jiraworkflow_ser.is_valid(raise_exception=True)
                # 根据升级工单名获取 SqlWorkflow 表数据
                # sql_workflow_obj = SqlWorkflow.objects.filter(workflow_name=current_summary)

                # 判断当前 webhook 状态，根据状态获取数据进行变更。每次转换状态前更新当前 issue DB 数据
                jiraworkflow_ser_data = dict(jiraworkflow_ser.validated_data)
                match current_status:
                    # SQL待执行 状态，可转变状态：无SQL升级/已升级 ｜ 提交SQL
                    case 'SQL待执行':
                        webhook_result = jira_event_webhook_obj.updated_event_sql_waiting(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jiraworkflow_ser_data,
                            sqlworkflow_ser=SqlWorkflowSerializer,
                            sql_workflow_ins=SqlWorkflow
                        )
                    # SQL执行中 状态，可转变状态：SQL升级成功 ｜ SQL升级失败
                    case 'SQL执行中':
                        webhook_result = jira_event_webhook_obj.updated_event_sql_inprogress(
                            sql_workflow_ins=SqlWorkflow,
                            current_issue_data=jiraworkflow_ser_data
                        )
                    # CONFIG执行中 状态，可转变状态：无配置升级/已升级 ｜ 配置升级成功 ｜ 配置升级失败
                    case 'CONFIG执行中':
                        webhook_result = jira_event_webhook_obj.updated_event_config_inprogress(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jiraworkflow_ser_data
                        )
                    # CODE执行中 状态，可转变状态：无代码升级/已升级 ｜ 代码升级成功 ｜ 代码升级失败
                    case 'CODE执行中':
                        webhook_result = jira_event_webhook_obj.updated_event_code_inprogress(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jiraworkflow_ser_data
                        )
                    case _:
                        sleep(1)
                        msg = f"工单：{current_summary} 当前 issue 状态为 <{current_status}>，不需要触发下一步流程，不更新 issue 数据，忽略状态转换"
                        webhook_result = {'status': True, 'msg': msg}
            else:
                raise KeyError('jira webhook event 事件不为 created 或 updated，请检查 webhook event 类型')
            # webhook 处理结果非 true 时，返回错误信息
            if not webhook_result['status']:
                d_logger.error(webhook_result)
                return Response(data=webhook_result, status=status.HTTP_400_BAD_REQUEST)
            # webhook 正常触发，记录返回日志
            d_logger.info(webhook_result)
            return Response(status=status.HTTP_200_OK)
        except KeyError as err:
            msg = {
                'status': False,
                'msg': 'webhook 数据中没有 created 或 updated 操作',
                'data': f"{err.__str__()}"
            }
            d_logger.error(f"{msg}")
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except Exception as err:
            msg = {
                'status': False,
                'msg': f"webhook 触发失败，异常原因：{err.__str__()}",
                'data': f"{err.__str__()}"
            }
            d_logger.error(f"{msg}")
            return Response(status=status.HTTP_400_BAD_REQUEST)

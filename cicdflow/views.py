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
from utils.cicdflow_util import JiraEventWebhookAPI, JiraAPI
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
        return_data = {
            'code': 10200,
            'msg': 'success',
            'data': {
                'summary': '',
                'upgrade_status': '',
                'sql_info': list(),
                'code_info': list()
            }
        }
        try:
            summary = request.GET.get('summary')
            sql_id = request.GET.get('sql_id')
            assert summary, "参数必选项 summary 参数缺失，工单编号名称为必需值"

            # 根据查询参数，查询 jira_workflow、sql_workflow 表
            jira_obj = JiraWorkflow.objects.get(summary=summary)

            # 返回工单名和升级状态
            status_map = {
                'UAT UPGRADED': 100,
                'SQL PENDING': 101,
                'SQL PROCESSING': 102,
                'SQL PROCESSING FAILED': 150,
                'CODE PROCESSING FAILED': 151
            }
            return_data['data']['summary'] = jira_obj.summary
            return_data['data']['upgrade_status'] = status_map.get(jira_obj.status, jira_obj.status)

            # 返回 sql 升级信息
            sql_info_list = list()
            # 存在 sql_id 查询参数时，只返回具体某个 sql 文件的执行结果
            if sql_id:
                sql_workflow_obj = SqlWorkflow.objects.get(sql_id=sql_id)
                tmp_dict = dict()
                tmp_dict['sql_id'] = sql_id
                tmp_dict['status'] = sql_workflow_obj.w_status
                tmp_dict['errormessage'] = ''
                sql_info_list.append(tmp_dict)
            else:
                # 引入 jira_api 与 archery_api
                from utils.jira_api import JiraAPI
                from utils.archery_api import ArcheryAPI
                jira_api_obj = JiraAPI()
                archery_obj = ArcheryAPI()

                # 获取 jira 升级数据
                issue_info = jira_api_obj.get_issue_info(issue_id=jira_obj.issue_id)
                sql_info_data = issue_info['data']['sql_info']
                sql_id_list = [item['sql_id'] for item in sql_info_data]

                # 只获取 jira 存在 sql_id 的数据
                sql_workflow_obj = SqlWorkflow.objects.filter(
                    workflow_name=summary,
                    sql_id__in=sql_id_list
                ).order_by('sql_index')
                # 获取 sql 工单对应字段转换为列表
                sql_workflow_list = [
                    row for row in sql_workflow_obj.values(
                        'w_id',
                        'workflow_name',
                        'w_status',
                        'sql_index',
                        'sql_release_info',
                        'sql_id',
                        'create_date'
                    )
                ]
                # sql_id 相同时，取 create_date 较大的值返回
                tmp_filtered_data = {}
                for item in sql_workflow_list:
                    sql_id = item['sql_id']
                    create_date = item['create_date']
                    if sql_id not in tmp_filtered_data or create_date > tmp_filtered_data[sql_id]['create_date']:
                        tmp_filtered_data[sql_id] = item
                filtered_sql_workflow_list = list(tmp_filtered_data.values())

                for sql_item in filtered_sql_workflow_list:
                    w_id = sql_item.get('w_id')
                    sql_id = sql_item.get('sql_id')
                    w_status = sql_item.get('w_status')
                    # sql_info 工单存在 exception 状态时，从 archery_api 接口获取 errormessage
                    if w_status == 'workflow_exception':
                        select_result = archery_obj.get_workflows(w_id=w_id)
                        errormessage = select_result['data'][0]['execute_result'][0]['errormessage']
                    else:
                        errormessage = ''
                    # 循环写入所有 sql 工单信息到 sql_info 列表中
                    tmp_dict = dict()
                    tmp_dict['sql_id'] = sql_id
                    tmp_dict['status'] = w_status
                    tmp_dict['errormessage'] = errormessage
                    sql_info_list.append(tmp_dict)

            # 返回 code 升级信息
            code_info_list = list()

            return_data['data']['sql_info'] = sql_info_list
            return_data['data']['code_info'] = code_info_list
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
            jira_api_obj = JiraAPI()

            # 调用 jira_api 创建或更新工单
            cicdflow_ser = CICDFlowSerializer(data=request.data)
            if cicdflow_ser.is_valid(raise_exception=True):
                # 获取序列化后的 request_data 数据
                cicdflow_ser_data = dict(cicdflow_ser.validated_data)

                # project 参数区分项目列表
                ac_project_list = [
                    'A22',
                    'QC',
                    'ISLOT',
                    'FPB',
                    'IS01',
                    'IS02',
                    'IS03',
                    'BW01'
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

                # 工单标题已存在，更新 Jira 工单并转换状态到 <StartUpgradeAgain> 进行迭代升级
                if jira_issue_obj_exists:
                    jira_issue_obj = jira_issue_obj_exists.get()
                    issue_key = jira_issue_obj.issue_key
                    issue_status = jira_issue_obj.status
                    # 判断 issue 状态是否为 <SQL PENDING> 或 <UAT UPGRADED>，非此状态抛出异常，不允许更新 issue 数据
                    if issue_status in ['UAT UPGRADED']:
                        d_logger.info(f"工单：{current_summary} 状态为 <UAT UPGRADED>，正常流转流程")
                        trans_result = jira_api_obj.change_transition(issue_key, 'StartUpgradeAgain')
                        if not trans_result['status']:
                            return_data['msg'] = f"已存在 Jira 工单，转换工单状态失败，错误原因：{trans_result['data']}"
                            d_logger.warning(return_data)
                        # 从 <UAT UPGRADED> 状态变更，开始迭代升级
                        else:
                            return_data['status'] = True
                            return_data['msg'] = '已存在 Jira 工单，转换工单状态到 <StartUpgradeAgain>，开始完整迭代升级流程。'
                            return_data['jira_issue_key'] = issue_key
                            d_logger.info(return_data)
                    # SQL PENDING 状态数据有变化时会自动触发 webhook，无需人为调用 change_transition 方法变更状态
                    elif issue_status in ['SQL PENDING', 'SQL PROCESSING FAILED']:
                        return_data['status'] = True
                        return_data['msg'] = f"工单：{current_summary} 状态为 <SQL PENDING> 或 <SQL PROCESSING FAILED>，重新提交 SQL 触发完整升级流程"
                        return_data['jira_issue_key'] = issue_key
                        d_logger.info(return_data)
                    elif issue_status in ['CODE PROCESSING FAILED', 'FIX PENDING']:
                        return_data['status'] = True
                        return_data['msg'] = f"工单：{current_summary} 状态为 <CODE PROCESSING FAILED> 或 <FIX PENDING>，开始完整迭代升级流程"
                        return_data['jira_issue_key'] = issue_key
                        jira_api_obj.issue_update(args=cicdflow_ser_data, issue_id=issue_key)
                        jira_api_obj.change_transition(issue_key, 'StartUpgradeAgain')
                        jira_api_obj.change_transition(issue_key, 'TriggerSubmitSQL')
                        d_logger.info(return_data)
                        return Response(data=return_data, status=status.HTTP_200_OK)
                    else:
                        return_data['msg'] = '当前工单 issue 状态非 <SQL PENDING> 或 <UAT UPGRADED> 或 <FIX PENDING> ，不允许开始升级流程，检查当前工单状态'
                        d_logger.warning(return_data)
                        return Response(data=return_data, status=status.HTTP_200_OK)
                    # 更新 Jira 工单，失败时抛出异常
                    update_result = jira_api_obj.issue_update(args=cicdflow_ser_data, issue_id=issue_key)
                    if not update_result['status']:
                        return_data['status'] = False
                        # jira 更新异常返回 JIRAError 类，需要转换为字符串
                        return_data['msg'] = update_result['data'].text
                        d_logger.warning(return_data)
                    return Response(data=return_data, status=status.HTTP_200_OK)
                # 不存在工单，新建 Jira 工单触发 issue_updated 事件
                else:
                    create_result = jira_api_obj.issue_create(args=cicdflow_ser_data)
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
        project in (AC, QC) and issuetype in (升级) and status in ("SQL PENDING,"SQL PROCESSING","CONFIG PROCESSING","CODE PROCESSING")
    webhook 判断：
        webhookEvent = jira:issue_created  --> 首次创建 jira issue，初始化升级数据，开始升级流程
        webhookEvent = jira:issue_updated  --> 迭代或重新提交升级，更新升级数据，已最新数据重跑升级流程
            SQL PENDING：判断是否存在 SQL，存在则提交到 Archery
            SQL PROCESSING：由 DBA 审核执行并人工触发进入下一步（UAT 为自动触发）
            CONFIG PROCESSING：由运维人员人工触发进入下一步
            CODE PROCESSING：判断是否有代码升级，存在则升级应用
    """
    def post(self,
             request,
             *args: Any,
             **kwargs: Any) -> Response:
        try:
            # 初始化并序列化 webhook http request data 数据
            jira_event_webhook_obj = JiraEventWebhookAPI(request.data)
            # 暂时不处理运营环境 webhook
            if jira_event_webhook_obj.webhook_env == 'PRO':
                raise Exception('运营环境跳过，不处理 webhook!!!!!!!!')

            # webhook 事件为 created 时，调用 created_event_operate 方法初始化工单与开始流程
            if jira_event_webhook_obj.webhook_event == 'jira:issue_created':
                jiraworkflow_ser = JiraWorkflowSerializer(data=jira_event_webhook_obj.webhook_data)
                jiraworkflow_ser.is_valid(raise_exception=True)
                webhook_result = jira_event_webhook_obj.created_event_operate(
                    current_issue_data=dict(jiraworkflow_ser.validated_data),
                    serializer=jiraworkflow_ser
                )

            # webhook 事件为 updated 时，判断当前 issue 状态，根据状态进行转换
            elif jira_event_webhook_obj.webhook_event == 'jira:issue_updated':
                # 获取当前 Jira webhook 表单中数据
                current_webhook_data = jira_event_webhook_obj.webhook_data
                current_issue_key = current_webhook_data.get('issue_key')
                current_status = current_webhook_data.get('status')
                current_summary = current_webhook_data.get('summary')
                # 获取 JiraWorkflow 表中的数据
                last_issue_obj = JiraWorkflow.objects.get(issue_key=current_issue_key)
                # 根据 JiraWorkflow 序列化器序列化当前 webhook 数据
                jiraworkflow_ser = JiraWorkflowSerializer(instance=last_issue_obj, data=current_webhook_data)
                jiraworkflow_ser.is_valid(raise_exception=True)
                # 根据升级工单名获取 SqlWorkflow 表数据
                # sql_workflow_obj = SqlWorkflow.objects.filter(workflow_name=current_summary)

                # 判断当前 webhook 状态，根据状态获取数据进行变更。每次转换状态前更新当前 issue DB 数据
                jiraworkflow_ser_data = dict(jiraworkflow_ser.validated_data)
                match current_status:
                    # SQL PENDING 状态，可转变状态：无SQL升级/已升级 ｜ 提交SQL
                    case 'SQL PENDING':
                        webhook_result = jira_event_webhook_obj.updated_event_sql_pending(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jiraworkflow_ser_data,
                            sqlworkflow_ser=SqlWorkflowSerializer,
                            sql_workflow_ins=SqlWorkflow
                        )
                    # SQL执行中 状态，可转变状态：SQL升级成功 ｜ SQL升级失败
                    case 'SQL PROCESSING':
                        webhook_result = jira_event_webhook_obj.updated_event_sql_processing(
                            last_issue_obj=last_issue_obj,
                            sql_workflow_ins=SqlWorkflow,
                            current_issue_data=jiraworkflow_ser_data
                        )
                    # CONFIG执行中 状态，可转变状态：无配置升级/已升级 ｜ 配置升级成功 ｜ 配置升级失败
                    case 'CONFIG PROCESSING':
                        webhook_result = jira_event_webhook_obj.updated_event_config_processing(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jiraworkflow_ser_data
                        )
                    # CODE执行中 状态，可转变状态：无代码升级/已升级 ｜ 代码升级成功 ｜ CODE PROCESSING FAILED
                    case 'CODE PROCESSING':
                        webhook_result = jira_event_webhook_obj.updated_event_code_processing(
                            last_issue_obj=last_issue_obj,
                            current_issue_data=jiraworkflow_ser_data
                        )
                    case 'FIX PENDING':
                        webhook_result = jira_event_webhook_obj.updated_event_fix_pending(
                            current_issue_key=current_issue_key
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


class CheckVersion(APIView):
    def get(self, request, *args, **kwargs):
        return_data = {
            'code': 10200,
            'msg': 'PROD UPGRADED',
            'data': list()
        }
        try:
            summary = request.GET.get('summary')
            assert summary, '参数必选项 summary 参数缺失，工单编号名称为必需值'

            # 获取工单实例
            jira_obj = JiraWorkflow.objects.get(summary=summary)
            from utils.cmdb_api import CmdbAPI
            cmdb = CmdbAPI()

            # 判断工单状态
            upgrade_status = jira_obj.status
            assert upgrade_status=='UAT UPGRADED', '当前 UAT 升级工单状态非 <UAT UPGRADED> 状态'

            # 获取升级版本数据判断
            all_code_info_list = jira_obj.code_info
            code_info_list = [x for x in all_code_info_list if 'uat' not in x['svn_path']]

            tmp_data = list()
            tmp_dict = dict()
            for code_info in code_info_list:
                cmdb_info_dict = cmdb.search_info(code_info['svn_path'])
                assert cmdb_info_dict['status'], '从 CMDB 获取线上数据失败！'

                tmp_dict['project_name'] = cmdb_info_dict['data']['project_name']
                tmp_dict['uat_tag'] = code_info['tag']
                tmp_dict['uat_version'] = code_info['svn_version']
                tmp_dict['prod_version'] = cmdb_info_dict['data']['project_version']
                tmp_data.append(tmp_dict)

            # 线上版本与当前 UAT 版本不一致
            prod_flag = [x for x in tmp_data if x['uat_version'] == x['prod_version']]
            if len(prod_flag) != len(tmp_data):
                return_data['code'] = 10209
                return_data['msg'] = 'UAT and PROD version are inconsistent'

            return_data['data'] = tmp_data
        except AssertionError as err:
            return_data['code'] = 10500
            return_data['msg'] = f"{err.__str__()}"
        except (JiraWorkflow.DoesNotExist, SqlWorkflow.DoesNotExist) as err:
            return_data['code'] = 10404
            return_data['msg'] = f"工单编号数据不存在，错误内容：{err.__str__()}"
        except Exception as err:
            return_data['code'] = 10500
            return_data['msg'] = f"接口异常，异常原因： {err.__str__()}"
        return Response(data=return_data, status=status.HTTP_200_OK)


from . import log_test
class YakirTest(APIView):
    def get(self, request, *args, **kwargs):
        return_data = {
            'code': 10200,
            'msg': 'log test to app.log',
            'data': list()
        }
        try:
            log_test.log_test()
        except Exception as err:
            return_data['code'] = 10500
            return_data['msg'] = f"接口异常，异常原因： {err.__str__()}"
        return Response(data=return_data, status=status.HTTP_200_OK)

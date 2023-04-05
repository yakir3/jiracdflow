from typing import Dict, List, Union, Any
from datetime import datetime
from time import sleep
import re
from collections import defaultdict
from django.db.models import Q

from util.jira_api import JiraWebhookData, JiraAPI
from util.cmdb_api import CmdbAPI
from util.archery_api import ArcheryAPI
from util.svn_client import SvnClient
from util.email_tool import EmailClient

__all__ = ['JiraEventWebhookAPI', 'JiraAPI']

# JIRA 实例，用于获取 issue 状态以及转换状态
jira_obj = JiraAPI()
# Email 实例，用于发送工单结束邮件
email_obj = EmailClient()


# 对比升级前后列表差值
def compare_list_info(last_list_info: List, current_list_info: List) -> List[Dict[str, Union[str, int]]]:
    compare_result = []
    for csi_item in current_list_info:
        found = False
        for lsi_item in last_list_info:
            if csi_item == lsi_item:
                found = True
                break
        if not found:
            compare_result.append(csi_item)
    return compare_result

# 代码升级完成发送邮件通知
def completed_workflow_notice(start_time: str, end_time: str, email_summary: str, project_list: List) -> Dict:
    project: str = '\n'.join(project_list) if None not in project_list else '无代码升级，SQL 或配置已升级到 UAT 环境'
    send_msg: str = f"""Dear All:

1. Upgrade start time:  {start_time}
2. Upgrade end   time:  {end_time}
3. Upgrader: API
4. The following content has been upgraded:

{project}
"""
    send_result = email_obj.send_email(send_msg, email_summary)
    return send_result

# 传入 Jira 表单中 sql 升级数据，返回 commit_data 数据，用于提交 Archery
def get_sql_commit_data(
        sql_data: Dict[str, Union[str, int]],
        current_sql_info: List,
        current_summary: str) -> Dict:
    svn_path = sql_data.get('svn_path')
    svn_version = sql_data.get('svn_version')
    svn_file = sql_data.get('svn_file')
    # 通过 svn 信息获取每个sql 文件与内容，根据内容提交sql工单
    svn_obj = SvnClient(svn_path)
    sql_content_value = svn_obj.get_file_content(revision=svn_version, filename=svn_file)
    # 提交 sql 序号，顺序执行 sql
    seq_index = current_sql_info.index(sql_data) + 1
    # DB 所属资源组名称：A18 ｜ A19 ｜ QC
    svn_path_up = svn_path.upper()
    if 'yakir' in svn_file:
        sql_resource_name = 'QC'
        sql_instance_name = 'uat_pg_env'
    elif 'AC' in svn_path_up:
        sql_resource_name = svn_path.split('/')[-2].split('_')[-1].upper()
        sql_instance_name = svn_path.split('/')[-1]
    elif 'QC' in svn_path_up:
        qc_ins_dict = {
            'rex_merchant': 'qc-merchant',
            'rex_admin': 'qc-admin',
            'rex_rpt': 'qc-report',
        }
        sql_resource_name = re.split(r'[/_]\s*', svn_path_up)[2]
        qc_ins_key = svn_path.split('/')[-1]
        # qc-merchant=bwup01, qc-admin=bwup02, qc-report=bwup03
        sql_instance_name = qc_ins_dict[qc_ins_key]
    else:
        raise ValueError("svn 路径不包含 ac 或 qc 关键字路径，请确认是否正确输入 svn 路径")
    commit_data = {
        'sql_index': int(seq_index),
        'sql_release_info': str(svn_version),
        'sql': sql_content_value,
        'workflow_name': current_summary,
        'resource_tag': sql_resource_name,
        'instance_tag': sql_instance_name
    }
    return commit_data

def filtered_queryset(
        queryset: Any
):
    rows = [row for row in queryset.values('w_id', 'workflow_name', 'w_status', 'sql_index', 'sql_release_info')]
    # 过滤 sql_index 和 workflow_name 字段相同数据时，取 sql_release_info 最大的数据
    max_sql_release_info = defaultdict(int)
    filtered_rows = []
    for row in rows:
        key = (row['sql_index'], row['workflow_name'])
        if row['sql_release_info'] > max_sql_release_info[key]:
            max_sql_release_info[key] = row['sql_release_info']
            filtered_rows = [r for r in filtered_rows if (r['sql_index'], r['workflow_name']) != key]
        if row['sql_release_info'] == max_sql_release_info[key]:
            filtered_rows.append(row)
    return filtered_rows

class JiraEventWebhookAPI(JiraWebhookData):
    def __init__(self, request_data: Dict):
        super().__init__(request_data)
        # 清洗 webhook 数据为 serializer 格式数据
        self.webhook_data = self.get_issue_data()
        # 暴露 webhook changelog 与事件类型（created 或 updated）
        self.webhook_from = self.webhook_data.pop('fromstring')
        self.webhook_to = self.webhook_data.pop('tostring')
        self.webhook_event = self.webhook_data.pop('webhook_event')
        # 触发 webhook 返回数据
        self._webhook_return_data = {
            'status': True,
            'msg': '',
            'data': dict()
        }
        self.webhook_env = self.webhook_data.get('environment')

    def created_event_operate(self, current_issue_data: Dict, serializer: Any=None) -> Dict[str, Union[str, dict]]:
        """
        webhook 事件为 created 时，Jira 工单初始化创建。判断是否有 SQL，并转换进行下一状态
        """
        try:
            current_issue_key = current_issue_data['issue_key']
            current_summary = current_issue_data['summary']
            current_sql_info = current_issue_data['sql_info']
            serializer.save()
            # 判断是否有 SQL 升级数据：触发进入下一步流程
            if not current_sql_info:
                self._webhook_return_data['msg'] = f"Jira工单被创建，工单名：{current_summary}，工单无SQL升级数据，触发转换 <无SQL升级/已升级> 到状态 <CONFIG执行中>"
                jira_obj.change_transition(current_issue_key, '无SQL升级/已升级')
            else:
                self._webhook_return_data['msg'] = f"Jira工单被创建，工单名：{current_summary}，工单有SQL升级数据，触发转换 <触发提交SQL> 到状态 <SQL待执行>"
                jira_obj.change_transition(current_issue_key, '触发提交SQL')
        except Exception as err:
            self._webhook_return_data['status'] = False
            self._webhook_return_data['msg'] = err.__str__()
        self._webhook_return_data['data'] = current_issue_data
        return self._webhook_return_data

    def updated_event_sql_waiting(self, last_issue_obj: Any, current_issue_data: Dict, sqlworkflow_ser: Any):
        """
        <待执行SQL> 状态，判断升级为首次升级或迭代升级
        """
        try:
            last_sql_info = last_issue_obj.sql_info
            # 是否为初始化首次升级标志，非0为迭代升级
            sql_init_flag = last_issue_obj.init_flag['sql_init_flag']
            current_issue_key = current_issue_data['issue_key']
            current_sql_info = current_issue_data['sql_info']
            current_summary = current_issue_data['summary']
            # current_project = current_issue_data['project']

            # 从<SQL执行中>状态转换来的 webhook 只更新数据不做操作
            if self.webhook_from == "SQL执行中":
                last_issue_obj.status = 'SQL待执行'
                # last_issue_obj.init_flag['sql_init_flag'] += 1
                last_issue_obj.save()
                self._webhook_return_data['msg'] = f"SQL执行失败，从<SQL执行中>状态转换不触发 webhook 操作，保持<SQL待执行>状态等待重新触发"
                return self._webhook_return_data

            # webhook 中 sql_info 数据为空，直接触发到下一流程
            sql_exists = bool(current_sql_info)
            if not sql_exists:
                last_issue_obj.status = 'CONFIG执行中'
                last_issue_obj.init_flag['sql_init_flag'] += 1
                last_issue_obj.save()
                jira_obj.change_transition(current_issue_key, '无SQL升级/已升级')
                self._webhook_return_data[
                    'msg'] = f"SQL 升级数据为空，自动触发进入下一流程。升级工单 {current_summary} 触发转换 <无SQL升级/已升级> 到状态 <CONFIG执行中>"
                return self._webhook_return_data

            # 初始化迭代升级 sql 数据
            if sql_init_flag:
                # 待升级的 sql_info 数据
                wait_commit_list = compare_list_info(last_sql_info, current_sql_info)
                # 已成功升级的 sql_info 数据
                commit_success_list = last_sql_info
                # 迭代升级，对比与上一次 webhook 中 sql_info 数据，无变化则触发跳过流程
                if not wait_commit_list:
                    last_issue_obj.status = 'CONFIG执行中'
                    last_issue_obj.init_flag['sql_init_flag'] += 1
                    last_issue_obj.save()
                    jira_obj.change_transition(current_issue_key, '无SQL升级/已升级')
                    self._webhook_return_data[
                        'msg'] = f"SQL 迭代升级数据无需变更，自动触发进入下一流程。升级工单 {current_summary} 触发转换 <无SQL升级/已升级> 到状态 <CONFIG执行中>"
                    return self._webhook_return_data
            # 初始化首次升级 sql 数据
            else:
                # 待升级的 sql_info 数据
                wait_commit_list = last_sql_info
                # 已成功升级的 sql_info 数据
                commit_success_list = []

            # 实例化 archery 对象，调用 commit_workflow 方法提交sql审核执行
            archery_obj = ArcheryAPI()
            # 提交成功的 sql 列表
            # upgrade_sql_name_list = []

            # 开始提交 sql 逻辑
            for sql_data in wait_commit_list:
                svn_version = sql_data['svn_version']
                svn_file = sql_data['svn_file']
                # 获取提交 Archery SQL 工单数据
                commit_data = get_sql_commit_data(sql_data, current_sql_info, current_summary)
                upgrade_result = archery_obj.commit_workflow(commit_data)
                # 每成功提交一次数据，追加数据到 last_sql_info 数据之后，有失败直接中断提交 SQL 循环流程
                if upgrade_result['status']:
                    commit_success_list.append(sql_data)
                    # 提交成功时，获取 SqlWorkflow 序列化器序列化提交 SQL 工单数据，保存入 sql_workflow 表，用于后续审核 & 执行同步工单状态
                    sql_ser = sqlworkflow_ser(data=upgrade_result['data'])
                    sql_ser.is_valid(raise_exception=True)
                    sql_ser.save()
                    print(f"SQL：{svn_file} 提交成功，提交版本：{svn_version}，对应工单：{current_issue_key}")
                else:
                    print(f"SQL：{svn_file} 提交失败，提交版本：{svn_version}，对应工单：{current_issue_key}，错误原因：{upgrade_result['msg']}")
                    break

            # 只有全部sql提交成功才转换为 <提交SQL>，只要有sql提交失败不转换状态
            if commit_success_list == current_sql_info or not compare_list_info(commit_success_list, current_sql_info):
                last_issue_obj.status = 'SQL执行中'
                last_issue_obj.sql_info = current_sql_info
                last_issue_obj.init_flag['sql_init_flag'] += 1
                last_issue_obj.save()
                self._webhook_return_data['msg'] = f"所有 SQL 提交成功，升级工单 {current_summary} 触发转换 <提交SQL> 到状态 <SQL执行中>"
                jira_obj.change_transition(current_issue_key, '提交SQL')
            else:
                last_issue_obj.sql_info = commit_success_list
                last_issue_obj.init_flag['sql_init_flag'] += 1
                last_issue_obj.save()
                self._webhook_return_data['msg'] = f"有 SQL 提交失败，升级工单 {current_summary} 保持 <SQL待执行> 状态等待修复"
                self._webhook_return_data['status'] = False
        except Exception as err:
            self._webhook_return_data['status'] = False
            self._webhook_return_data['msg'] = f"<SQL待执行> 状态 webhook 触发失败，异常原因：{err.__str__()}"
        # self._webhook_return_data['data'] = current_issue_data
        return self._webhook_return_data

    def updated_event_sql_inprogress(self, sql_workflow_obj: Any, current_issue_data: Dict):
        """
        <SQL执行中> 状态，按升级序号顺序 审核+执行 SQL 工单，出现异常则中断执行
        """
        current_issue_key = current_issue_data['issue_key']
        # current_sql_info = current_issue_data['sql_info']
        current_summary = current_issue_data['summary']

        # 过滤 sql_workflow QuerySet 数据中 sql_release_info 最大的数据
        sql_workflow_obj = sql_workflow_obj.objects.filter(workflow_name=current_summary)

        try:
            # 获取并判断 SQL 工单状态
            # workflow_manreviewing：将所有 SQL 工单都转换为 <workflow_review_pass> 状态，一旦存在审核失败，将 Jira 状态触发 <SQL执行失败> 转换到 <SQL待执行>
            # workflow_review_pass：按顺序执行 SQL 工单，一旦失败终止当前及后续 SQL 工单，将 Jira 状态转换为 <SQL待执行>
            # workflow_queuing ｜ workflow_exception：终止流程
            # workflow_finish：所有工单执行完成，将 Jira 状态触发 <SQL执行成功> 转换到 <CONFIG执行中>
            archery_obj = ArcheryAPI()

            # 开始自动审核，使用 filtered_queryset 函数过滤出 sql_index workflow_name 相同时，sql_release_info 较大的值
            sql_workflow_list = filtered_queryset(sql_workflow_obj)
            for sql_workflow_data in sql_workflow_list:
                # SQL 工单 ID，通过唯一 ID 查询结果
                w_id = sql_workflow_data['w_id']
                select_result = archery_obj.get_workflows(args={'id': w_id})
                # 工单为待审核状态时，调用 archery 方法审核通过工单
                sql_workflow_status = select_result['data'][0]['status']
                sql_workflow_ins = sql_workflow_obj.get(**sql_workflow_data)
                if sql_workflow_status == 'workflow_manreviewing':
                    audit_result = archery_obj.audit_workflow(workflow_id=w_id)
                    # 工单自动审核失败，不继续审核。将 Jira 工单转换为 <SQL待执行> 状态
                    if not audit_result['status']:
                        self._webhook_return_data['status'] = False
                        self._webhook_return_data['msg'] = f"工单 {current_summary} 有 SQL 自动审核失败，失败原因：{audit_result['data']}"
                        jira_obj.change_transition(current_issue_key, 'SQL升级失败')
                        break
                    sql_workflow_ins.w_status = 'workflow_review_pass'
                else:
                    sql_workflow_ins.w_status = sql_workflow_status
                # 保存状态到 sql_workflow 表
                sql_workflow_ins.save()
            # 自动审核结束，查看升级工单对应的所有 SQL 工单状态是否已都是 workflow_review_pass | workflow_finish 状态
            after_audit_filtered_list = filtered_queryset(sql_workflow_obj)
            after_audit_list = [
                item for item in after_audit_filtered_list
                if item['w_status'] == 'workflow_manreviewing' or
                   item['w_status'] == 'workflow_queuing' or
                   item['w_status'] == 'workflow_abort' or
                   item['w_status'] == 'workflow_exception'
            ]
            # exclude_pass_obj = sql_workflow_obj.exclude(
            #     Q(w_status='workflow_review_pass') | Q(w_status='workflow_finish')
            # )
            # if exclude_pass_obj:
            if after_audit_list:
                self._webhook_return_data['status'] = False
                self._webhook_return_data['msg'] = f"工单 {current_summary} 自动审核正常结束，但存在有非 <审核通过> 状态的工单"
                jira_obj.change_transition(current_issue_key, 'SQL升级失败')
                return self._webhook_return_data

            # 开始自动执行，从 after_audit_filtered_list 中获取待执行的工单（已过滤出 sql_index workflow_name 相同时，sql_release_info 较大的值）
            for sql_workflow_data in after_audit_filtered_list:
                # SQL 工单 ID，通过唯一 ID 查询结果
                w_id = sql_workflow_data['w_id']
                select_result = archery_obj.get_workflows(args={'id': w_id})
                # 工单为审核通过时，调用 archery 方法执行工单
                sql_workflow_status = select_result['data'][0]['status']
                sql_workflow_ins = sql_workflow_obj.get(**sql_workflow_data)
                if sql_workflow_status == 'workflow_review_pass':
                    execute_result = archery_obj.execute_workflow(workflow_id=w_id)
                    # 工单自动执行失败，终止执行。将 Jira 工单转换为 <SQL待执行> 状态
                    if not execute_result['status']:
                        self._webhook_return_data['status'] = False
                        self._webhook_return_data[
                            'msg'] = f"工单 {current_summary} 有 SQL 自动执行失败，失败原因：{execute_result['data']}"
                        jira_obj.change_transition(current_issue_key, 'SQL升级失败')
                        break
                    # 成功执行后等待10s，否则工单可能为 workflow_queuing 状态。等待10s后再次查询状态，不成功终止后续 SQL 自动执行
                    sleep(10)
                    select_execute_result = archery_obj.get_workflows(args={'id': w_id})
                    execute_status = select_execute_result['data'][0]['status']
                    if not execute_status == 'workflow_finish':
                        self._webhook_return_data['status'] = False
                        self._webhook_return_data[
                            'msg'] = f"工单 {current_summary} 有 SQL 自动执行失败，失败原因：{execute_result['data']}"
                        jira_obj.change_transition(current_issue_key, 'SQL升级失败')
                        break
                    sql_workflow_ins.w_status = 'workflow_finish'
                else:
                    sql_workflow_ins.w_status = sql_workflow_status
                sql_workflow_ins.save()
            # 自动执行结束，查看状态是否已都是 workflow_finish 状态
            after_execute_filtered_list = filtered_queryset(sql_workflow_obj)
            after_execute_list = [
                item for item in after_execute_filtered_list
                if not item['w_status'] == 'workflow_finish'
            ]
            if after_execute_list:
                self._webhook_return_data['status'] = False
                self._webhook_return_data[
                    'msg'] = f"工单 {current_summary} 自动执行正常结束，但存在有非 <已正常结束> 状态的工单"
                return self._webhook_return_data

            self._webhook_return_data[
                'msg'] = f"升级工单 {current_summary} 所有 SQL 执行成功，触发转换 <SQL升级成功> 到状态 <CONFIG执行中>"
            jira_obj.change_transition(current_issue_key, 'SQL升级成功')
        except Exception as err:
            self._webhook_return_data['status'] = False
            self._webhook_return_data['msg'] = f"<SQL执行中> 状态 webhook 触发失败，异常原因：{err.__str__()}"
        # self._webhook_return_data['data'] = current_issue_data
        return self._webhook_return_data

    def updated_event_config_inprogress(self, last_issue_obj: Any, current_issue_data: Dict):
        """
        <CONFIG执行中> 状态，判断流程为首次升级或迭代升级
        """
        try:
            # last_apollo_info = last_issue_obj.apollo_info
            # last_config_info = last_issue_obj.config_info
            # # 是否为初始化首次升级标志，非0为迭代升级
            # apollo_init_flag = last_issue_obj.init_flag['apollo_init_flag']
            # config_init_flag = last_issue_obj.init_flag['config_init_flag']
            current_issue_key = current_issue_data['issue_key']
            current_apollo_info = current_issue_data['apollo_info']
            current_config_info = current_issue_data['config_info']
            current_summary = current_issue_data['summary']

            # webhook 中 apollo_info / config_info 数据为空，直接触发到下一流程
            apollo_exists = bool(current_apollo_info)
            config_exists = bool(current_config_info)
            if not apollo_exists and not config_exists:
                last_issue_obj.status = 'CODE执行中'
                last_issue_obj.init_flag['apollo_init_flag'] += 1
                last_issue_obj.init_flag['config_init_flag'] += 1
                last_issue_obj.save()
                jira_obj.change_transition(current_issue_key, '无配置升级/已升级')
                self._webhook_return_data[
                    'msg'] = f"Apollo/配置文件为空，自动触发进入下一流程。升级工单 {current_summary} 触发转换 <无配置升级/已升级> 到状态 <CODE执行中>"
                return self._webhook_return_data
            # 暂时不自动处理配置升级
            self._webhook_return_data['msg'] = f"升级工单 {current_summary} 存在 Apollo/配置文件 升级，不触发状态转换，人工介入处理"
            return self._webhook_return_data

            # # 迭代升级，对比与上一次 webhook 中 apollo_info config_info 数据，无变化则触发下一步）
            # if apollo_init_flag or config_init_flag:
            #     apollo_diff_list = compare_list_info(last_apollo_info, current_apollo_info)
            #     config_diff_list = compare_list_info(last_config_info, current_config_info)
            #     # webhook 中 apollo_info 与 config_info 数据与上次升级数据无对比差值，直接触发下一流程
            #     if not apollo_diff_list and not config_diff_list:
            #         last_issue_obj.status = 'CODE执行中'
            #         last_issue_obj.init_flag['apollo_init_flag'] += 1
            #         last_issue_obj.init_flag['config_init_flag'] += 1
            #         last_issue_obj.save()
            #         jira_obj.change_transition(current_issue_key, '无配置升级/已升级')
            #         self._webhook_return_data['msg'] = f"Apollo/配置文件无需变更，自动触发进入下一流程。升级工单 {current_summary} 触发转换 <无配置升级/已升级> 到状态 <CODE执行中>"
            #         return self._webhook_return_data
            #
            #     # TODO: 配置需要变更，此处调用 Apollo 或 Gitlab 接口进行变更？按返回状态自动转换下一步流程
            #     last_issue_obj.apollo_info = current_apollo_info
            #     last_issue_obj.config_info = current_config_info
            #     last_issue_obj.init_flag['apollo_init_flag'] += 1
            #     last_issue_obj.init_flag['config_init_flag'] += 1
            #     last_issue_obj.save()
            #     self._webhook_return_data['msg'] = 'Apollo/配置文件需要迭代升级，由运维人工变更并手动触发进入下一步流程，忽略自动触发操作'
            # # 首次升级，用 DB 中 apollo_info config_info 数据直接升级
            # else:
            #     # TODO: 配置需要变更此处调用 Apollo 或 Gitlab 接口进行变更？按返回状态自动转换下一步流程
            #     last_issue_obj.init_flag['apollo_init_flag'] += 1
            #     last_issue_obj.init_flag['config_init_flag'] += 1
            #     last_issue_obj.save()
            #     self._webhook_return_data['msg'] = 'Apollo/配置文件不为空且首次升级，由运维人工变更并手动触发进入下一步流程，忽略自动触发操作'
        except Exception as err:
            self._webhook_return_data['status'] = False
            self._webhook_return_data['msg'] = f"<CONFIG执行中> 状态 webhook 触发失败，异常原因：{err.__str__()}"
        self._webhook_return_data['data'] = current_issue_data
        return self._webhook_return_data

    def updated_event_code_inprogress(self, last_issue_obj: Any, current_issue_data: Dict):
        try:
            last_code_info = last_issue_obj.code_info
            code_init_flag = last_issue_obj.init_flag['code_init_flag']
            current_issue_key = current_issue_data['issue_key']
            current_code_info = current_issue_data['code_info']
            current_summary = current_issue_data['summary']
            # current_environment = current_issue_data['environment']

            # webhook 中 code_info 数据为空，直接触发到下一流程
            code_exists = bool(current_code_info)
            if not code_exists:
                last_issue_obj.status = 'UAT升级完成'
                last_issue_obj.init_flag['code_init_flag'] += 1
                last_issue_obj.save()
                jira_obj.change_transition(current_issue_key, '无代码升级/已升级')
                self._webhook_return_data[
                    'msg'] = f"代码升级数据为空，自动触发进入下一流程\n升级工单 {current_summary} 触发转换 <无代码升级/已升级> 到状态 <UAT升级完成>"
                return self._webhook_return_data

            # 初始化迭代升级代码数据
            if code_init_flag:
                # 待升级的 code_info 数据
                wait_upgrade_list = compare_list_info(last_code_info, current_code_info)
                # 已成功升级的 code_info 数据
                upgrade_success_list = last_code_info
                # 迭代升级，对比与上一次 webhook 中 code_info 数据，无变化则触发跳过流程
                if not wait_upgrade_list:
                    last_issue_obj.status = 'UAT升级完成'
                    last_issue_obj.init_flag['code_init_flag'] += 1
                    last_issue_obj.save()
                    jira_obj.change_transition(current_issue_key, '无代码升级/已升级')
                    self._webhook_return_data[
                        'msg'] = f"代码迭代升级数据无需变更，自动触发进入下一流程\n升级工单 {current_summary} 触发转换 <无代码升级/已升级> 到状态 <UAT升级完成>"
                    return self._webhook_return_data
            # 初始化首次升级代码数据
            else:
                # 待升级的 code_info 数据
                wait_upgrade_list = last_code_info
                # 已成功升级的 code_info 数据
                upgrade_success_list = []

            # 实例化 cmdb 对象，调用 upgrade 方法升级代码
            cmdb_obj = CmdbAPI()
            # 升级成功的工程名称列表，用于发送升级答复邮件
            upgrade_project_name_list = []

            print('开始升级代码.....')
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # 延迟升级，等待 harbor 镜像同步到 gcp
            sleep(120)
            for code_data in wait_upgrade_list:
                svn_path = code_data['svn_path']
                svn_version = code_data['svn_version']
                tag = code_data['tag']
                # upgrade_result = cmdb_obj.upgrade(env=current_environment, svn_path=svn_path, version=version, tag=tag)
                upgrade_result = cmdb_obj.upgrade(env='UAT', svn_path=svn_path, version=svn_version, tag=tag)
                if upgrade_result['status']:
                    upgrade_success_list.append(code_data)
                    upgrade_project_name_list.append(upgrade_result['data'][0]['project'])
                    print(f"svn路径 {svn_path} 对应工程升级成功，升级版本：{svn_version}，升级tag：{tag}")
                else:
                    print(f"svn路径 {svn_path} 对应工程升级失败，升级版本：{svn_version}，升级tag：{tag}，错误原因：{upgrade_result['msg']}")
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print('代码升级结束.....')

            # 只有全部升级成功才转换为<代码升级成功>，只要有失败的升级就转换为<代码升级失败>
            if upgrade_success_list == current_code_info or not compare_list_info(upgrade_success_list,
                                                                                  current_code_info):
                last_issue_obj.status = 'UAT升级完成'
                last_issue_obj.code_info = current_code_info
                last_issue_obj.init_flag['code_init_flag'] += 1
                last_issue_obj.save()
                self._webhook_return_data[
                    'msg'] = f"所有代码升级成功，升级工单 {current_summary} 触发转换 <代码升级成功> 到状态 <UAT升级完成>"
                self._webhook_return_data['data'] = {"已升级工程列表": upgrade_project_name_list}
                # # 打印升级代码结果
                # print(generate_template(start_time, end_time, upgrade_project_name_list))
                # 升级结果发送邮件
                print(completed_workflow_notice(start_time, end_time,current_summary, upgrade_project_name_list))
                jira_obj.change_transition(current_issue_key, '代码升级成功')
            else:
                last_issue_obj.status = '代码升级失败'
                last_issue_obj.code_info = upgrade_success_list
                last_issue_obj.init_flag['code_init_flag'] += 1
                last_issue_obj.save()
                self._webhook_return_data['status'] = False
                self._webhook_return_data[
                    'msg'] = f"代码升级失败，升级工单 {current_summary} 触发转换 <代码升级失败> 到状态 <开发/运维修改>"
                jira_obj.change_transition(current_issue_key, '代码升级失败')
        except Exception as err:
            self._webhook_return_data['status'] = False
            self._webhook_return_data['msg'] = f"<CODE执行中> 状态 webhook 触发失败，异常原因：{err.__str__()}"
        return self._webhook_return_data
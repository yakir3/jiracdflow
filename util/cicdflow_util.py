from typing import Dict, List, Union, Any, Tuple
from datetime import datetime
from time import sleep
import re
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict, UserDict
from django.db.models import Q

from util.jira_api import JiraWebhookData, JiraAPI
from util.cmdb_api import CmdbAPI
from util.archery_api import ArcheryAPI
from util.svn_client import SvnClient
from util.email_tool import EmailClient
from util.pgsql_api import PostgresClient

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
def completed_workflow_notice(start_time: str, end_time: str, email_summary: str, upgrade_info_list: List) -> Dict:
    upgrade_content: str = '\n'.join(upgrade_info_list) if None not in upgrade_info_list else '无代码升级，SQL 或配置已升级到 UAT 环境'
    send_msg: str = f"""Dear All:

1. Upgrade start time:  {start_time}
2. Upgrade end   time:  {end_time}
3. Upgrader: API
4. The following content has been upgraded:

{upgrade_content}
"""
    send_result = email_obj.send_email(send_msg, email_summary)
    return send_result

# 传入 Jira 表单中 sql 升级数据，返回 commit_data 和 bk_commit_data 数据，用于提交 Archery
def get_sql_commit_data(
        sql_data: Dict[str, Union[str, int]],
        current_sql_info: List,
        current_summary: str) -> Tuple[Union[None, Dict], Union[None, Dict]]:

    svn_path = sql_data.get('svn_path')
    svn_version = sql_data.get('svn_version')
    svn_file = sql_data.get('svn_file')
    # 根据 has_deploy_uat 字段值判断是否需要提交 SQL
    has_deploy_uat_flag = sql_data.get('has_deploy_uat')

    if not has_deploy_uat_flag:
        # 通过 svn 信息获取每个sql 文件与内容，根据内容提交sql工单
        svn_obj = SvnClient(svn_path)
        sql_content_value = svn_obj.get_file_content(revision=svn_version, filename=svn_file)

        # 增加审核功能，sql_content_value 工单内容不允许 create 语句设置 timestamp 属性，需要为 timestamp(0)
        audit_timestamp = re.findall(' timestamp[,\s]', sql_content_value)
        assert not audit_timestamp, "工单内容存在 timestamp 属性定义，不提交工单，检查 sql 内容。"

        # 提交 sql 序号，顺序执行 sql
        seq_index = current_sql_info.index(sql_data) + 1
        # DB 所属资源组名称：A18 ｜ A19 ｜ QC
        svn_path_up = svn_path.upper()
        ### yakir_test
        if 'yakir' in svn_file:
            sql_resource_name = 'QC'
            sql_instance_name = 'uat_pg_env'
            table_catalog = 'dbtest'
            bk_sql_content_value = get_backup_commit_data(table_catalog, sql_content_value)
            bk_commit_data = {
                'sql_index': int(seq_index),
                'sql_release_info': str(svn_version),
                'sql': bk_sql_content_value,
                'workflow_name': f"{current_summary}_备份工单",
                'resource_tag': sql_resource_name,
                'instance_tag': sql_instance_name
            } if bk_sql_content_value else None
        ###
        elif 'AC' in svn_path_up:
            sql_resource_name = svn_path.split('/')[-2].split('_')[-1].upper()
            sql_instance_name = svn_path.split('/')[-1]
            bk_commit_data = None
        elif 'QC' in svn_path_up:
            qc_ins_dict = {
                'rex_merchant_qc': 'qc-merchant',
                'rex_admin': 'qc-admin',
                'rex_rpt': 'qc-report',
                'rex_merchant_b01': 'b01_merchant',
                'rex_merchant_rs8': 'rs8_merchant'
            }
            sql_resource_name = re.split(r'[/_]\s*', svn_path_up)[2]
            qc_ins_key = svn_path.split('/')[-1]
            sql_instance_name = qc_ins_dict[qc_ins_key]

            # 备份库 SQL 信息获取
            bk_sql_content_value = get_backup_commit_data(sql_instance_name, sql_content_value)
            bk_commit_data = {
                'sql_index': int(seq_index),
                'sql_release_info': str(svn_version),
                'sql': bk_sql_content_value,
                'workflow_name': f"{current_summary}_备份工单",
                'resource_tag': sql_resource_name,
                'instance_tag': sql_instance_name
            } if bk_sql_content_value else None
        elif 'ISLOT' in svn_path_up:
            sql_resource_name = svn_path.split('/')[1].upper()
            sql_instance_name = svn_path.split('/')[1]
            bk_commit_data = None
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
        return commit_data, bk_commit_data
    else:
        print(f"{svn_path} 下 SQL: {svn_file} 已在 UAT 环境执行，版本号: {svn_version}")
        return None, None

def get_backup_commit_data(sql_instance_name: str, sql_content_value: str) -> Union[None, str]:
    try:
        # 解析原始的 dml sql，如果存在 delete update 语句则获取 delete update 语句
        sql_list = re.split(r";\s*$", sql_content_value, flags=re.MULTILINE)
        dml_sql_list = [sql.strip() for sql in sql_list if 'delete ' in sql.lower() or 'update ' in sql.lower()]
        if not dml_sql_list:
            return None

        # 从 sql 内容获取表名等信息，组装为备份 sql 语句
        bk_sql_content_value = ""
        bk_table_flag = []
        for sql in dml_sql_list:
            r_matches = re.search(r'(?:delete\sfrom|update)\s(\w+).*(where .*)', sql, flags=re.IGNORECASE|re.DOTALL)
            if not r_matches:
                continue
            # 初始化 pg 类，获取是否存在备份表
            pg_obj = PostgresClient(sql_instance_name)
            # 获取备份表名，同一工单同个表多个备份
            bk_table_name_list = pg_obj.select_bk_table(table_name=r_matches.group(1))
            if not bk_table_flag:
                bk_table_flag = bk_table_name_list
                bk_table_name = '_'.join(bk_table_name_list)
            else:
                bk_table_flag[2] = str(int(bk_table_flag[2]) + 1)
                bk_table_name = '_'.join(bk_table_flag)
            bk_sql_content = f"create table {bk_table_name} as select * from {r_matches.group(1)} {r_matches.group(2)};"
            bk_sql_content_value += f"{bk_sql_content}\n"
        return bk_sql_content_value
    except Exception as err:
        print(err.__str__())
        return None

# def filtered_queryset(
#         queryset: Any
# ):
#     rows = [row for row in queryset.values('w_id', 'workflow_name', 'w_status', 'sql_index', 'sql_release_info', 'sql_id')]
#     # 过滤 sql_index 和 workflow_name 字段相同数据时，取 sql_release_info 最大的数据
#     max_sql_release_info = defaultdict(int)
#     filtered_rows = []
#     for row in rows:
#         key = (row['sql_index'], row['workflow_name'])
#         if row['sql_release_info'] > max_sql_release_info[key]:
#             max_sql_release_info[key] = row['sql_release_info']
#             filtered_rows = [r for r in filtered_rows if (r['sql_index'], r['workflow_name']) != key]
#         if row['sql_release_info'] == max_sql_release_info[key]:
#             filtered_rows.append(row)
#     return filtered_rows

def thread_upgrade_code(wait_upgrade_list: List, upgrade_success_list: List, upgrade_info_list: List) -> Tuple:
    # 实例化 cmdb 对象，调用 upgrade 方法升级代码
    cmdb_obj = CmdbAPI()

    # 延迟升级，等待 harbor 镜像同步到 gcp
    if len(wait_upgrade_list) <= 3:
        sleep(30)
    elif 3 < len(wait_upgrade_list) <= 6:
        sleep(75)
    else:
        sleep(90)
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = []
        # 循环待升级代码列表，调用 cmdb_obj.upgrade 方法升级代码
        for code_data in wait_upgrade_list:
            # code_data['env'] = current_environment
            code_data['env'] = 'UAT'
            future = executor.submit(cmdb_obj.upgrade, **code_data)
            futures.append(future)
        # 获取升级结果列表，根据列表状态返回升级结果
        upgrade_results = [future.result() for future in futures]
        print(upgrade_results)
        for upgrade_result in upgrade_results:
            code_data_info = upgrade_result['code_data']
            upgr_p = upgrade_result['data'][0]['project']
            # code_data_info.pop('env')
            fail_msg = f"svn 路径 {code_data_info['svn_path']} 对应工程升级失败，升级版本：{code_data_info['svn_version']}，升级tag：{code_data_info['tag']}，错误原因：{upgrade_result['msg']}"
            success_msg = f"svn 路径 {code_data_info['svn_path']} 对应工程升级成功，升级版本：{code_data_info['svn_version']}，升级tag：{code_data_info['tag']}"
            if upgrade_result['status']:
                upgrade_success_list.append(code_data_info)
                if upgr_p:
                    # prod 工程不做升级
                    if upgr_p == "no_project":
                        print(f"{upgrade_result['msg']}")
                    else:
                        upgrade_info_list.append(f"{upgrade_result['data'][0]['project']:35s} 升级版本: {code_data_info['svn_version']}")
                        print(success_msg)
                # 没有升级工程，只有 SQL 或配置升级
                else:
                    upgrade_info_list.append(None)
                    print(f"{upgrade_result['msg']}")
            else:
                print(fail_msg)
                retry_flag = 0
                # 代码升级失败重试机制，等待10s重试2次升级
                while retry_flag < 2:
                    print(fail_msg)
                    sleep(10)
                    retry_result = cmdb_obj.upgrade(**code_data_info)
                    if retry_result['status']:
                        upgrade_success_list.append(code_data_info)
                        upgrade_info_list.append(f"{retry_result['data'][0]['project']:35s} 升级版本: {code_data_info['svn_version']}")
                        print(success_msg)
                        break
                    retry_flag += 1
        return upgrade_success_list, upgrade_info_list

# 自定义定长字典类
class LimitedDict(UserDict):
    def __init__(self, limit, *args, **kwargs):
        self.limit = limit
        super().__init__(*args, **kwargs)
    def __setitem__(self, key, value):
        if len(self) >= self.limit:
            raise ValueError("Dictionary is full")
        super().__setitem__(key, value)
# 定义定长全局字典，每次 SQL 升级存入标识，根据标识添加回复内容
sql_upgrade_flag: LimitedDict = LimitedDict(20)


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

    def updated_event_sql_waiting(self, last_issue_obj: Any, current_issue_data: Dict, sqlworkflow_ser: Any, sql_workflow_ins: Any):
        """
        <待执行SQL> 状态，判断升级为首次升级或迭代升级
        """
        # webhook 触发先更新 SqlWorkflow 表数据，进入<SQL待执行>状态
        last_issue_obj.status = 'SQL待执行'
        last_issue_obj.save()

        try:
            # last_sql_info = last_issue_obj.sql_info
            current_issue_key = current_issue_data['issue_key']
            current_sql_info = current_issue_data['sql_info']
            # 过滤掉只在运营执行的 SQL
            current_sql_info = [item for item in current_sql_info if '运营' not in item['svn_file']]
            current_summary = current_issue_data['summary']
            # current_project = current_issue_data['project']

            # 实例化 archery 对象，调用 commit_workflow 方法提交sql审核执行
            archery_obj = ArcheryAPI()

            # 从<SQL执行中>状态转换来的 webhook 只更新数据不做操作
            if self.webhook_from == "SQL执行中":
                last_issue_obj.status = 'SQL执行失败'
                # last_issue_obj.init_flag['sql_init_flag'] += 1
                last_issue_obj.save()
                self._webhook_return_data['msg'] = f"从<SQL执行中>状态转换而来，不触发 webhook 操作，保持<SQL待执行>状态等待重新触发"
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

            # Jira 的 sql_info 数据中对比当前所有需要提交 SQL 工单是否已全部存入 SqlWorkflow 表中
            commit_sql_list = [item for item in current_sql_info if not item['has_deploy_uat']]
            # webhook 中 sql_info 数据所有 has_deploy_uat 字段值都为 True, 直接触发到下一流程
            if not commit_sql_list:
                last_issue_obj.status = 'CONFIG执行中'
                last_issue_obj.init_flag['sql_init_flag'] += 1
                last_issue_obj.save()
                jira_obj.change_transition(current_issue_key, '无SQL升级/已升级')
                self._webhook_return_data[
                    'msg'] = f"SQL 升级已在 UAT 环境执行，无需重复执行。升级工单 {current_summary} 触发转换 <无SQL升级/已升级> 到状态 <CONFIG执行中>"
                return self._webhook_return_data

            # 轮循当前 sql_info 数据，根据 has_deploy_uat 值判断是否需要提交 SQL
            for sql_data in current_sql_info:
                svn_version = sql_data['svn_version']
                svn_file = sql_data['svn_file']
                sql_id = sql_data.get('sql_id')

                # 获取提交 Archery SQL 工单数据
                commit_data, bk_commit_data = get_sql_commit_data(sql_data, current_sql_info, current_summary)

                # 判断本次 SQL 升级是否需要提交备份工单，备份工单提交失败打印消息，不退出
                if bk_commit_data:
                    bk_sql_workflow_obj = sql_workflow_ins.objects.filter(
                        workflow_name=current_summary,
                        sql_id=sql_id,
                    ).filter(Q(w_status='workflow_manreviewing')| Q(w_status='workflow_review_pass') | Q(w_status='workflow_finish'))
                    if not bk_sql_workflow_obj:
                        try:
                            upgrade_bk_result = archery_obj.commit_workflow(bk_commit_data)
                            bk_name = bk_commit_data.get('workflow_name')
                            assert upgrade_bk_result['status'], f"备份工单 {bk_name} 提交失败"
                            upgrade_bk_result['data']['sql_id'] = sql_id
                            sql_ser = sqlworkflow_ser(data=upgrade_bk_result['data'])
                            sql_ser.is_valid(raise_exception=True)
                            sql_ser.save()
                            print(f'备份工单{bk_name}提交成功。')
                        except Exception as err:
                            print(f'备份工单提交/保存记录异常，异常原因：{err.__str__()}')

                # 判断本次 SQL 升级是否需要提交升级工单
                if commit_data:
                    # 先查询 SqlWorkflow 表是否已存在 SQL，如已存在则已提交过，不重复提交。
                    sql_workflow_obj = sql_workflow_ins.objects.filter(
                        workflow_name=current_summary,
                        sql_id=sql_id,
                        # sql_index=commit_data['sql_index']
                    ).filter(Q(w_status='workflow_manreviewing')| Q(w_status='workflow_review_pass') | Q(w_status='workflow_finish'))
                    if not sql_workflow_obj:
                        # 调用 archery_api commit 方法提交 SQL
                        commit_result = archery_obj.commit_workflow(commit_data)
                        # 成功提交 SQL 则存入 SqlWorkflow 表
                        if commit_result['status']:
                            # 提交成功时，获取 SqlWorkflow 序列化器序列化提交 SQL 工单数据，保存入 sql_workflow 表，用于后续审核和执行同步工单状态
                            commit_result['data']['sql_id'] = sql_id
                            sql_ser = sqlworkflow_ser(data=commit_result['data'])
                            sql_ser.is_valid(raise_exception=True)
                            sql_ser.save()
                            print(f"SQL：{svn_file} 提交成功，提交版本：{svn_version}，对应工单：{current_issue_key}")
                        else:
                            print(f"SQL：{svn_file} 提交失败，提交版本：{svn_version}，对应工单：{current_issue_key}，错误原因：{commit_result['data']}")

            # 只有全部 SQL 提交成功才转换为 <SQL执行中>，只要有 SQL 提交失败不转换状态
            commit_success_list = []
            for sql_item in commit_sql_list:
                sql_workflow_obj = sql_workflow_ins.objects.filter(
                    workflow_name=current_summary,
                    sql_id=sql_item['sql_id']
                ).filter(Q(w_status='workflow_manreviewing') | Q(w_status='workflow_review_pass') | Q(
                    w_status='workflow_finish'))
                if sql_workflow_obj:
                    commit_success_list.append(1)

            last_issue_obj.sql_info = current_sql_info
            last_issue_obj.init_flag['sql_init_flag'] += 1
            if len(commit_sql_list) == len(commit_success_list):
                self._webhook_return_data['msg'] = f"所有待执行 SQL 提交成功，升级工单 {current_summary} 触发转换 <提交SQL> 到状态 <SQL执行中>"
                jira_obj.change_transition(current_issue_key, '提交SQL')
            else:
                self._webhook_return_data['status'] = False
                self._webhook_return_data['msg'] = f"存在待执行 SQL 工单提交失败，升级工单 {current_summary} 保持 <SQL待执行> 状态等待修复"
        except Exception as err:
            self._webhook_return_data['status'] = False
            self._webhook_return_data['msg'] = f"<SQL待执行> 状态 webhook 触发失败，异常原因：{err.__str__()}"
        return self._webhook_return_data

    def updated_event_sql_inprogress(self, last_issue_obj: Any, sql_workflow_ins: Any, current_issue_data: Dict):
        """
        <SQL执行中> 状态，按升级序号顺序 审核+执行 SQL 工单，出现异常则中断执行
        """
        # webhook 触发先更新 SqlWorkflow 表数据，进入<SQL执行中>状态
        last_issue_obj.status = 'SQL执行中'
        last_issue_obj.save()

        current_issue_key = current_issue_data['issue_key']
        current_sql_info = current_issue_data['sql_info']
        current_summary = current_issue_data['summary']
        current_code_info = current_issue_data['code_info']

        # 初始化 Archery 实例，用于操作工单
        archery_obj = ArcheryAPI()

        # 获取 SqlWorkflow 表中所有待审核状态的备份工单
        bk_sql_workflow_obj = sql_workflow_ins.objects.filter(
            workflow_name=f'{current_summary}_备份工单',
            w_status='workflow_manreviewing'
        )
        # 判断是否存在需要备份工单，先执行备份工单再执行后续 SQL
        if bk_sql_workflow_obj:
            bk_sql_list = [row for row in bk_sql_workflow_obj.values('w_id')]
            for bk_sql_item in bk_sql_list:
                bk_sql_wid = bk_sql_item['w_id']
                try:
                    # 审核备份工单
                    audit_result = archery_obj.audit_workflow(workflow_id=bk_sql_wid)
                    assert audit_result['status'], "工单 {} 审核失败，错误原因 {}".format(bk_sql_wid, audit_result)
                    # 执行备份工单
                    execute_result = archery_obj.execute_workflow(workflow_id=bk_sql_wid)
                    assert execute_result['status'], "工单 {} 执行失败，错误原因 {}".format(bk_sql_wid, execute_result)
                    # 审核+执行成功，修改工单状态，保存到 SqlWorkflow 表
                    bk_sql_workflow_ins = bk_sql_workflow_obj.get(w_id=bk_sql_wid)
                    bk_sql_workflow_ins.w_status = 'workflow_finish'
                    bk_sql_workflow_ins.save()
                except AssertionError as err:
                    print(f'备份工单审核或执行异常，异常原因：{err.__str__()}')
        else:
            print(f'本次 SQL 升级备份工单为空，无需备份.')

        try:
            # 获取并判断 SQL 工单状态
            # workflow_manreviewing：将所有 SQL 工单都转换为 <workflow_review_pass> 状态，一旦存在审核失败，将 Jira 状态触发 <SQL执行失败> 转换到 <SQL待执行>
            # workflow_review_pass：按顺序执行 SQL 工单，一旦失败终止当前及后续 SQL 工单，将 Jira 状态转换为 <SQL待执行>
            # workflow_queuing / workflow_exception：终止流程
            # workflow_finish：所有工单执行完成，将 Jira 状态触发 <SQL执行成功> 转换到 <CONFIG执行中>

            # 开始升级 SQL
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f'开始执行 SQL，开始时间：{start_time}')

            # 获取 SqlWorkflow 表中所有待审核状态的 SQL 工单，已 sql_index 为排序顺序
            audit_sql_obj = sql_workflow_ins.objects.filter(
                workflow_name=current_summary,
                w_status='workflow_manreviewing'
            ).order_by('sql_index')
            # 开始自动审核
            audit_sql_list = [row for row in audit_sql_obj.values(
                'w_id',
                'workflow_name',
                'w_status',
                'sql_index',
                'sql_release_info',
                'sql_id')]
            for audit_sql_data in audit_sql_list:
                # SQL 工单 ID，通过唯一 ID 查询结果
                w_id = audit_sql_data['w_id']
                select_result = archery_obj.get_workflows(args={'id': w_id})
                sql_workflow_status = select_result['data'][0]['status']
                audit_ins = audit_sql_obj.get(**audit_sql_data)
                # 工单为待审核状态时，调用 archery_api 方法审核通过工单
                if sql_workflow_status == 'workflow_manreviewing':
                    audit_result = archery_obj.audit_workflow(workflow_id=w_id)
                    # 工单自动审核失败，不继续审核。将 Jira 工单转换为 <SQL待执行> 状态
                    if not audit_result['status']:
                        self._webhook_return_data['status'] = False
                        self._webhook_return_data['msg'] = f"工单 {current_summary} 有 SQL 自动审核失败，失败原因：{audit_result['data']}"
                        jira_obj.change_transition(current_issue_key, 'SQL升级失败')
                        break
                    audit_ins.w_status = 'workflow_review_pass'
                else:
                    audit_ins.w_status = sql_workflow_status
                # 保存状态到 sql_workflow 表
                audit_ins.save()
            # 自动审核结束，确认是否还存在 workflow_manreviewing 状态工单
            if audit_sql_obj:
                self._webhook_return_data['status'] = False
                self._webhook_return_data['msg'] = f"工单 {current_summary} 自动审核正常结束，但存在有非 <审核通过> 状态的工单"
                jira_obj.change_transition(current_issue_key, 'SQL升级失败')
                return self._webhook_return_data

            # 获取 SqlWorkflow 表中所有审核通过状态的 SQL 工单
            sql_id_list = [item['sql_id'] for item in current_sql_info if not item['has_deploy_uat']]
            execute_sql_obj = sql_workflow_ins.objects.filter(
                workflow_name=current_summary,
                w_status='workflow_review_pass',
                sql_id__in=sql_id_list
            ).order_by('sql_index')
            # 开始自动执行，根据 current_sql_info 中 sql_id 获取需要审核执行的 sql
            execute_sql_list = [row for row in execute_sql_obj.values(
                'w_id',
                'workflow_name',
                'w_status',
                'sql_index',
                'sql_release_info',
                'sql_id')]
            # 只有 sql_id 存在且 has_deploy_uat 为 False 的工单才执行
            for execute_sql_data in execute_sql_list:
                # SQL 工单 ID，通过唯一 ID 查询结果
                w_id = execute_sql_data['w_id']
                # select_result = archery_obj.get_workflows(args={'id': w_id})
                # sql_workflow_status = select_result['data'][0]['status']
                execute_ins = execute_sql_obj.get(**execute_sql_data)

                # 工单为审核通过时，调用 archery_api 方法执行工单
                execute_result = archery_obj.execute_workflow(workflow_id=w_id)
                # 工单自动执行失败，终止执行。将 Jira 工单转换为 <SQL待执行> 状态
                if not execute_result['status']:
                    self._webhook_return_data['status'] = False
                    self._webhook_return_data[
                        'msg'] = f"工单 {current_summary}  SQL 调用 archery 执行 SQL 接口失败，失败原因：{execute_result['data']}"
                    jira_obj.change_transition(current_issue_key, 'SQL升级失败')
                    break
                # 成功执行后等待15s，否则工单可能为 workflow_queuing 状态。等待后再次查询状态，不成功终止后续 SQL 自动执行
                sleep(15)
                select_execute_result = archery_obj.get_workflows(args={'id': w_id})
                execute_status = select_execute_result['data'][0]['status']
                execute_ins.w_status = execute_status
                execute_ins.save()
                print(f"{current_summary} SQL 执行成功, SQL 版本: {execute_sql_data['sql_release_info']}, SQL ID: {execute_sql_data['sql_id']}")
                if not execute_status == 'workflow_finish':
                    self._webhook_return_data['status'] = False
                    self._webhook_return_data[
                        'msg'] = f"工单 {current_summary}  存在执行结果为异常的 SQL，失败原因：{execute_result['data']}"
                    jira_obj.change_transition(current_issue_key, 'SQL升级失败')
                    break
            # 自动执行结束，核实是否还存在 workflow_review_pass 状态工单
            if execute_sql_obj:
                self._webhook_return_data['status'] = False
                self._webhook_return_data[
                    'msg'] = f"工单 {current_summary} 自动执行正常结束，但存在有非 <已正常结束> 状态的工单"
                return self._webhook_return_data

            # 已工单标题为 key，全局 SQL 升级标识
            global sql_upgrade_flag
            sql_upgrade_flag[current_summary] = 1

            # SQl 升级结束，无代码升级则直接发出邮件
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f'执行 SQL 结束，结束时间：{end_time}')
            if not current_code_info:
                upgrade_info_list = []
                try:
                    sql_upgrade_flag.pop(current_summary)
                    upgrade_info_list.append("SQL 已升级到 UAT 环境")
                except KeyError:
                    pass
                print(completed_workflow_notice(start_time, end_time, current_summary, upgrade_info_list))

            # SQL 升级成功，转换 Jira 工单状态
            self._webhook_return_data[
                'msg'] = f"升级工单 {current_summary} 所有 SQL 执行成功，触发转换 <SQL升级成功> 到状态 <CONFIG执行中>"
            jira_obj.change_transition(current_issue_key, 'SQL升级成功')
        except AssertionError as err:
            self._webhook_return_data['status'] = False
            self._webhook_return_data['msg'] = err.__str__()
        except Exception as err:
            self._webhook_return_data['status'] = False
            self._webhook_return_data['msg'] = f"<SQL执行中> 状态 webhook 触发失败，异常原因：{err.__str__()}"
        # self._webhook_return_data['data'] = current_issue_data
        return self._webhook_return_data

    def updated_event_config_inprogress(self, last_issue_obj: Any, current_issue_data: Dict):
        """
        <CONFIG执行中> 状态，判断流程为首次升级或迭代升级
        """
        # webhook 触发先更新 SqlWorkflow 表数据，进入<CONFIG执行中>状态
        last_issue_obj.status = 'CONFIG执行中'
        last_issue_obj.save()

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

            apollo_exists = bool(current_apollo_info)
            config_exists = bool(current_config_info)
            apollo_has_deploy = [item for item in current_apollo_info if item['has_deploy_uat'] is not True]
            config_has_deploy = [item for item in current_config_info if item['has_deploy_uat'] is not True]
            # 保存 apollo_info 与 config_info 数据到 SqlWorkflow 表
            last_issue_obj.apollo_info = current_apollo_info
            last_issue_obj.config_info = current_config_info
            # webhook 中 apollo_info 与 config_info 数据都为空，直接触发到下一流程
            if not apollo_exists and not config_exists:
                # last_issue_obj.status = 'CODE执行中'
                last_issue_obj.init_flag['apollo_init_flag'] += 1
                last_issue_obj.init_flag['config_init_flag'] += 1
                last_issue_obj.save()
                jira_obj.change_transition(current_issue_key, '无配置升级/已升级')
                self._webhook_return_data[
                    'msg'] = f"Apollo与配置文件为空，自动触发进入下一流程。升级工单 {current_summary} 触发转换 <无配置升级/已升级> 到状态 <CODE执行中>"
                return self._webhook_return_data
            # apollo_info 或 config_info 数据只要不为空，判断 has_deploy_uat 字段是否存在 False
            elif not apollo_has_deploy and not config_has_deploy:
                # last_issue_obj.status = 'CODE执行中'
                last_issue_obj.init_flag['apollo_init_flag'] += 1
                last_issue_obj.init_flag['config_init_flag'] += 1
                last_issue_obj.save()
                jira_obj.change_transition(current_issue_key, '无配置升级/已升级')
                self._webhook_return_data[
                    'msg'] = f"Apollo与配置文件已升级 UAT 环境，自动触发进入下一流程。升级工单 {current_summary} 触发转换 <无配置升级/已升级> 到状态 <CODE执行中>"
                return self._webhook_return_data

            # 卡住流程，等待人工处理
            self._webhook_return_data['msg'] = f"升级工单 {current_summary} 存在 Apollo/配置文件 升级，不触发状态转换，人工介入处理"
            return self._webhook_return_data
        except Exception as err:
            self._webhook_return_data['status'] = False
            self._webhook_return_data['msg'] = f"<CONFIG执行中> 状态 webhook 触发失败，异常原因：{err.__str__()}"
        self._webhook_return_data['data'] = current_issue_data
        return self._webhook_return_data

    def updated_event_code_inprogress(self, last_issue_obj: Any, current_issue_data: Dict):
        last_code_info = last_issue_obj.code_info
        code_init_flag = last_issue_obj.init_flag['code_init_flag']
        current_issue_key = current_issue_data['issue_key']
        current_code_info = current_issue_data['code_info']
        current_summary = current_issue_data['summary']
        # current_environment = current_issue_data['environment']

        # webhook 触发先更新 SqlWorkflow 表数据，进入<CODE执行中>状态
        last_issue_obj.status = 'CODE执行中'
        last_issue_obj.save()

        try:
            # webhook 中 code_info 数据为空，直接触发到下一流程
            code_exists = bool(current_code_info)
            if not code_exists:
                last_issue_obj.status = 'UAT升级完成'
                last_issue_obj.init_flag['code_init_flag'] += 1
                last_issue_obj.code_info = current_code_info
                last_issue_obj.save()
                jira_obj.change_transition(current_issue_key, '无代码升级/已升级')
                self._webhook_return_data[
                    'msg'] = f"代码升级数据为空，自动触发进入下一流程\n升级工单 {current_summary} 触发转换 <无代码升级/已升级> 到状态 <UAT升级完成>"
                return self._webhook_return_data

            # current_code_info 数据调整
            for item in current_code_info:
                if item['tag'] == '':
                    item['tag'] = 'v1'
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
                        'msg'] = f"代码迭代升级数据为空，自动触发进入下一流程\n升级工单 {current_summary} 触发转换 <无代码升级/已升级> 到状态 <UAT升级完成>"
                    return self._webhook_return_data
            # 初始化首次升级代码数据
            else:
                # 待升级的 code_info 数据
                wait_upgrade_list = last_code_info
                # 已成功升级的 code_info 数据
                upgrade_success_list = []

            # 升级成功的工程名称列表，用于发送升级答复邮件
            upgrade_info_list = []

            # 升级代码主逻辑
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f'开始升级代码，开始时间：{start_time}')
            upgrade_success_list, upgrade_info_list = thread_upgrade_code(wait_upgrade_list, upgrade_success_list, upgrade_info_list)
            end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f'代码升级结束，结束时间：{end_time}')

            # current_code_info 数据调整
            current_code_info = [{k: v for k, v in d.items() if k != 'env'} for d in current_code_info]

            # 只有全部升级成功才转换为<代码升级成功>，只要有失败的升级就转换为<代码升级失败>
            if upgrade_success_list == current_code_info or not compare_list_info(
                    upgrade_success_list,
                    current_code_info):
                last_issue_obj.status = 'UAT升级完成'
                last_issue_obj.code_info = current_code_info
                last_issue_obj.init_flag['code_init_flag'] += 1
                last_issue_obj.save()
                self._webhook_return_data[
                    'msg'] = f"所有代码升级成功，升级工单 {current_summary} 触发转换 <代码升级成功> 到状态 <UAT升级完成>"
                self._webhook_return_data['data'] = {"已升级信息列表": upgrade_info_list}
                # 升级结果发送邮件
                global sql_upgrade_flag
                try:
                    sql_upgrade_flag.pop(current_summary)
                    upgrade_info_list.append("SQL 已升级到 UAT 环境")
                except KeyError:
                    # print(f'工单 {current_summary} 本次无 SQL 升级')
                    pass
                print(completed_workflow_notice(start_time, end_time, current_summary, upgrade_info_list))
                jira_obj.change_transition(current_issue_key, '代码升级成功')
            else:
                last_issue_obj.status = '代码升级失败'
                last_issue_obj.code_info = upgrade_success_list
                last_issue_obj.init_flag['code_init_flag'] += 1
                last_issue_obj.save()
                self._webhook_return_data['status'] = False
                self._webhook_return_data[
                    'msg'] = f"代码升级失败，升级工单 {current_summary} 触发转换 <代码升级失败> 到状态 <开发/运维修改>"
                # self._webhook_return_data['data'] = current_issue_data
                jira_obj.change_transition(current_issue_key, '代码升级失败')
        except Exception as err:
            self._webhook_return_data['status'] = False
            self._webhook_return_data['msg'] = f"<CODE执行中> 状态 webhook 触发失败，异常原因：{err.__str__()}"
            jira_obj.change_transition(current_issue_key, '代码升级失败')
        return self._webhook_return_data
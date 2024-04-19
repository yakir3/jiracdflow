from typing import Dict, List, Union, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
# from collections import defaultdict, UserDict
from django.db.models import Q
from time import sleep
import traceback
import re

from cicdflow.models import SqlWorkflow
from cicdflow.serializers import SqlWorkflowSerializer

from utils.archery_api import ArcheryAPI
from utils.cmdb_api import CmdbAPI
from utils.getconfig import GetYamlConfig
from utils.git_utils import get_sql_content as get_sql_content_from_gitlab
from utils.nacos_client import NacosClient
from utils.svn_client import SvnClient
from utils.pgsql_api import PostgresClient
from utils.email_client import EmailClient
email_obj = EmailClient()
import logging
d_logger = logging.getLogger("default_logger")

__all__ = [
    # sql
    "format_sql_info",
    "sql_submit_handle",
    "sql_upgrade_handle",
    # nacos
    "format_nacos_info",
    "nacos_handle",
    # code
    "format_code_info",
    "compare_list_info",
    "completed_workflow_notice",
    "thread_code_handle"
]

# 格式化 sql 升级数据
def format_sql_info(
        sql_info: str = None,
) -> List:
    sql_info_list = []
    if sql_info:
        for i in sql_info.split("\r\n"):
            item = {
                "repo_name": i.split("@@")[0],
                "file_name": i.split("@@")[1],
                "commit_sha": i.split("@@")[2],
            }
            sql_info_list.append(item)
    return sql_info_list

# 提交 SQL 到 Archery 处理函数
def sql_submit_handle(
        workflow_name: str = "",
        sql_info: str = None,
        environment: str = "UAT",
):
    return_data = {
        "status": False,
        "msg": "",
        "data": dict()
    }
    try:
        # 格式化 sql_info 数据
        sql_info_list = format_sql_info(sql_info)

        # 获取 Archery  配置信息
        archery_config = GetYamlConfig().get_config("Archery")
        assert archery_config, "获取 Archery 或 Gitlab 配置信息失败，检查 config.yaml 配置文件。"
        archery_username = archery_config.get("username")
        archery_password = archery_config.get("password")
        # 获取 Gitlab 配置信息
        gitlab_config = GetYamlConfig().get_config('Gitlab')
        gitlab_host = gitlab_config.get("host")
        gitlab_token = gitlab_config.get("private_token")


        # 根据 environment 获取对应 Archery 配置; 过滤掉只在对应环境执行的 SQL
        if environment == "PROD":
            archery_host = archery_config.get("prod_host")
            real_sql_info_list = [item for item in sql_info_list if "ONLYUAT" not in item["file_name"]]
        else:
            archery_host = archery_config.get("uat_host")
            real_sql_info_list = [item for item in sql_info_list if "ONLYPROD" not in item["file_name"]]
        archery_host = archery_config.get("uat_host")

        # 创建 Archery 对象，调用 commit_workflow 方法提交 SQL
        archery_obj = ArcheryAPI(
            host=archery_host,
            username=archery_username,
            password=archery_password
        )

        # 创建 SqlWorkflow, SqlWorkflowSerializer 对象
        sqlworkflow_obj = SqlWorkflow()
        sqlworkflow_ser_obj = SqlWorkflowSerializer()

        # 开始提交处理逻辑
        submit_success_number = 0
        for sql_index, sql_data in real_sql_info_list:
            sql_index = sql_index + 1
            repo_name = sql_data.get("repo_name")
            file_name = sql_data("file_name")
            commit_sha = sql_data("commit_sha")
            sql_resource_name = repo_name.split("_")[0].upper()
            sql_instance_name = repo_name.split("_")[1]

            # 查询 SqlWorkflow 表是否已存在 SQL 文件，不存在则提交，存在则跳过
            existed_flag = sqlworkflow_obj.objects.filter(
                workflow_name=workflow_name,
                sql_file_name=file_name,
                sql_release_info=commit_sha
            ).filter(
                Q(w_status="workflow_manreviewing") | Q(w_status="workflow_review_pass") | Q(w_status="workflow_finish")
            )
            if existed_flag:
                submit_success_number += 1
                continue

            # 获取提交 Archery SQL 工单数据
            commit_data = {
                "sql_index": sql_index,
                'sql_release_info': commit_sha,
                "sql_content": get_sql_content_from_gitlab(
                    server_address=gitlab_host,
                    private_token=gitlab_token,
                    repo_name=repo_name,
                    file_name=file_name,
                    commit_sha=commit_sha
                ),
                "workflow_name": workflow_name,
                "resource_tag": sql_resource_name,
                "instance_tag": sql_instance_name,
            }
            # 提交工单，提交成功保存如 SqlWorkflow 表
            commit_result = archery_obj.commit_workflow(**commit_data)
            if commit_result["status"]:
                submit_success_number += 1
                commit_result['data']['sql_filename'] = file_name
                sqlworkflow_ser = sqlworkflow_ser_obj(data=commit_result['data'])
                sqlworkflow_ser.is_valid(raise_exception=True)
                sqlworkflow_ser.save()
                d_logger.info(f"工单：{workflow_name} SQL：{file_name} 提交成功，提交版本：{commit_sha}")
            else:
                d_logger.error(f"工单：{workflow_name} SQL：{file_name} 提交失败，提交版本：{commit_sha}")

            # TODO: 获取提交 Archery SQL 备份工单数据

        # 当前工单所有 SQL 文件提交成功
        if len(real_sql_info_list) == submit_success_number:
            return_data["status"] = True
            return_data["msg"] = "SQL 文件提交到 Archery 成功"
        # 存在 SQL 文件提交失败
        else:
            return_data["msg"] = "SQL 文件提交到 Archery 失败，检查日志"
    except Exception as err:
        return_data["msg"] = f"SQL 文件提交到 Archery 异常，异常原因：{traceback.format_exc()}"
    return return_data

# 调用 Archery 接口自动执行工单函数
def sql_upgrade_handle(
        sql_info: str = None,
        environment: str = "UAT"
):
    # 初始化 Archery 实例，用于操作工单
    archery_obj = ArcheryAPI()

    # 判断是否存在需要备份工单，先执行备份工单再执行后续 SQL
    # 获取 SqlWorkflow 表中所有待审核状态的备份工单
    bk_sql_workflow_obj = sql_workflow_ins.objects.filter(
        workflow_name=f"{current_summary}_备份工单",
        w_status="workflow_manreviewing"
    )
    if bk_sql_workflow_obj:
        bk_sql_list = [row for row in bk_sql_workflow_obj.values("w_id")]
        for bk_sql_item in bk_sql_list:
            bk_sql_wid = bk_sql_item["w_id"]
            try:
                # 审核备份工单
                audit_result = archery_obj.audit_workflow(workflow_id=bk_sql_wid)
                assert audit_result["status"], "工单 {} 审核失败，错误原因 {}".format(bk_sql_wid, audit_result)
                # 执行备份工单
                execute_result = archery_obj.execute_workflow(workflow_id=bk_sql_wid)
                assert execute_result["status"], "工单 {} 执行失败，错误原因 {}".format(bk_sql_wid, execute_result)
                # 审核+执行成功，修改工单状态，保存到 SqlWorkflow 表
                bk_sql_workflow_ins = bk_sql_workflow_obj.get(w_id=bk_sql_wid)
                bk_sql_workflow_ins.w_status = "workflow_finish"
                bk_sql_workflow_ins.save()
            except AssertionError as err:
                d_logger.error(f"备份工单审核或执行异常，异常原因：{err.__str__()}")
    else:
        d_logger.info(f"本次 SQL 升级备份工单为空，无需备份.")

    try:
        # 获取并判断 SQL 工单状态
        # workflow_manreviewing：将所有 SQL 工单都转换为 <workflow_review_pass> 状态，一旦存在审核失败，将 Jira 状态触发 <SQL执行失败> 转换到 <SQL PENDING>
        # workflow_review_pass：按顺序执行 SQL 工单，一旦失败终止当前及后续 SQL 工单，将 Jira 状态转换为 <SQL PENDING>
        # workflow_queuing / workflow_exception：终止流程
        # workflow_finish：所有工单执行完成，将 Jira 状态触发 <SQL执行成功> 转换到 <CONFIG PROCESSING>

        # 开始升级 SQL
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        d_logger.info(f"工单 {current_summary} 开始执行 SQL，开始时间：{start_time}")

        # 获取 SqlWorkflow 表中所有待审核状态的 SQL 工单，已 sql_index 为排序顺序
        audit_sql_obj = sql_workflow_ins.objects.filter(
            workflow_name=current_summary,
            w_status="workflow_manreviewing"
        ).order_by("sql_index")
        # 开始自动审核
        audit_sql_list = [row for row in audit_sql_obj.values(
            "w_id",
            "workflow_name",
            "w_status",
            "sql_index",
            'sql_release_info',
            'sql_id')]
        for audit_sql_data in audit_sql_list:
            # SQL 工单 ID，通过唯一 ID 查询结果
            w_id = audit_sql_data["w_id"]
            select_result = archery_obj.get_workflows(w_id=w_id)
            sql_workflow_status = select_result['data'][0]["status"]
            audit_ins = audit_sql_obj.get(**audit_sql_data)
            # 工单为待审核状态时，调用 archery_api 方法审核通过工单
            if sql_workflow_status == "workflow_manreviewing":
                audit_result = archery_obj.audit_workflow(workflow_id=w_id)
                # 工单自动审核失败，不继续审核。将 Jira 工单转换为 <SQL PENDING> 状态
                if not audit_result["status"]:
                    self.webhook_return_data["status"] = False
                    self.webhook_return_data[
                        "msg"] = f"工单 {current_summary} 有 SQL 自动审核失败，失败原因：{audit_result['data']}"
                    jira_obj.change_transition(current_issue_key, "SQLUpgradeFailed")
                    break
                audit_ins.w_status = "workflow_review_pass"
            else:
                audit_ins.w_status = sql_workflow_status
            # 保存状态到 sql_workflow 表
            audit_ins.save()
        # 自动审核结束，确认是否还存在 workflow_manreviewing 状态工单
        if audit_sql_obj:
            self.webhook_return_data["status"] = False
            self.webhook_return_data[
                "msg"] = f"工单 {current_summary} 自动审核正常结束，但存在有非 <审核通过> 状态的工单"
            jira_obj.change_transition(current_issue_key, "SQLUpgradeFailed")
            return self.webhook_return_data

        # 获取 SqlWorkflow 表中所有审核通过状态的 SQL 工单
        sql_id_list = [item['sql_id'] for item in current_sql_info if not item["has_deploy_uat"]]
        execute_sql_obj = sql_workflow_ins.objects.filter(
            workflow_name=current_summary,
            w_status="workflow_review_pass",
            sql_id__in=sql_id_list
        ).order_by("sql_index")
        # 开始自动执行，根据 current_sql_info 中 sql_id 获取需要审核执行的 sql
        execute_sql_list = [row for row in execute_sql_obj.values(
            "w_id",
            "workflow_name",
            "w_status",
            "sql_index",
            'sql_release_info',
            'sql_id')]
        # 只有 sql_id 存在且 has_deploy_uat 为 False 的工单才执行
        for execute_sql_data in execute_sql_list:
            # SQL 工单 ID，通过唯一 ID 查询结果
            w_id = execute_sql_data["w_id"]
            # select_result = archery_obj.get_workflows(w_id=w_id)
            # sql_workflow_status = select_result['data'][0]["status"]
            execute_ins = execute_sql_obj.get(**execute_sql_data)

            # 工单为审核通过时，调用 archery_api 方法执行工单
            execute_result = archery_obj.execute_workflow(workflow_id=w_id)
            # 工单自动执行失败，终止执行。将 Jira 工单转换为 <SQL PENDING> 状态
            if not execute_result["status"]:
                self.webhook_return_data["status"] = False
                self.webhook_return_data[
                    "msg"] = f"工单 {current_summary}  SQL 调用 archery 执行 SQL 接口失败，失败原因：{execute_result['data']}"
                jira_obj.change_transition(current_issue_key, "SQLUpgradeFailed")
                break
            # 成功触发执行后等待15s，否则工单可能为 workflow_queuing | workflow_executing 状态。等待后再次查询状态，不成功终止后续 SQL 自动执行
            # sleep(15)
            select_execute_result = archery_obj.get_workflows(w_id=w_id)
            execute_status = select_execute_result['data'][0]["status"]
            execute_ins.w_status = execute_status
            execute_ins.save()
            d_logger.info(
                f"{current_summary} SQL 执行成功, SQL 版本: {execute_sql_data['sql_release_info']}, SQL ID: {execute_sql_data['sql_id']}")
            if not execute_status == "workflow_finish":
                self.webhook_return_data["status"] = False
                self.webhook_return_data[
                    "msg"] = f"工单 {current_summary}  存在执行结果为异常的 SQL，失败原因：{execute_result['data']}"
                jira_obj.change_transition(current_issue_key, "SQLUpgradeFailed")
                break
        # 自动执行结束，核实是否还存在 workflow_review_pass 状态工单
        if execute_sql_obj:
            self.webhook_return_data["status"] = False
            self.webhook_return_data[
                "msg"] = f"工单 {current_summary} 自动执行正常结束，但存在有非 <已正常结束> 状态的工单"
            return self.webhook_return_data

        # SQl 升级结束，无代码升级则直接发出邮件
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        d_logger.info(f"工单 {current_summary} 执行 SQL 结束，结束时间：{end_time}")
        if not current_code_info or not compare_list_info(last_sql_info, current_code_info):
            upgrade_info_list = []
            d_logger.info(completed_workflow_notice(start_time, end_time, current_summary, upgrade_info_list))

        # SQL 升级成功，转换 Jira 工单状态
        self.webhook_return_data[
            "msg"] = f"升级工单 {current_summary} 所有 SQL 执行成功，触发转换 <SQLUpgradeSuccessful> 到状态 <CONFIG PROCESSING>"
        jira_obj.change_transition(current_issue_key, "SQLUpgradeSuccessful")
    except AssertionError as err:
        self.webhook_return_data["status"] = False
        self.webhook_return_data["msg"] = err.__str__()

# 根据 sql 语句生成备份工单数据
def get_backup_commit_data(
        sql_instance_name: str,
        sql_content_value: str
) -> Union[None, str]:
    try:
        # 解析原始的 dml sql，如果存在 delete update 语句则获取 delete update 语句
        sql_list = re.split(r";\s*$", sql_content_value, flags=re.MULTILINE)
        dml_sql_list = [sql.strip() for sql in sql_list if "delete " in sql.lower() or "update " in sql.lower()]
        if not dml_sql_list:
            return None

        # 从 sql 内容获取表名等信息，组装为备份 sql 语句
        bk_sql_content_value = ""
        bk_table_flag = []
        for sql in dml_sql_list:
            r_matches = re.search(r"(?:delete\sfrom|update)\s(\w+).*(where .*)", sql, flags=re.IGNORECASE|re.DOTALL)
            if not r_matches:
                continue
            # 初始化 pg 类，获取是否存在备份表
            pg_obj = PostgresClient(sql_instance_name)
            # 获取备份表名，同一工单同个表多个备份
            bk_table_name_list = pg_obj.select_bk_table(table_name=r_matches.group(1))
            if not bk_table_flag:
                bk_table_flag = bk_table_name_list
                bk_table_name = "bk" + "_".join(bk_table_name_list)
            else:
                bk_table_flag[2] = str(int(bk_table_flag[2]) + 1)
                bk_table_name = "bk" + "_".join(bk_table_flag)
            bk_sql_content = f"create table {bk_table_name} as select * from {r_matches.group(1)} {r_matches.group(2)};"
            bk_sql_content_value += f"{bk_sql_content}\n"
        return bk_sql_content_value
    except Exception as err:
        d_logger.error(err.__str__())
        return None

# 格式化 nacos 数据
def format_nacos_info(
        nacos_info: str = None
) -> Dict:
    nacos_info_dict = {}
    if nacos_info:
        for i in nacos_info.split("\r\n"):
            columns = i.split("@@")
            data_id = columns[0]
            item = {
                "action": columns[1],
                "key": columns[2],
                "value": columns[3] if columns[1] != "delete" else None,
            }
            if data_id in nacos_info_dict:
                nacos_info_dict[data_id].append(item)
            else:
                nacos_info_dict[data_id] = []
                nacos_info_dict[data_id].append(item)
    return nacos_info_dict

def nacos_handle(
        nacos_info: str = None,
        product_id: str = None,
        environment: str = None
):
    return_data = {
        "status": False,
        "msg": "",
        "data": dict()
    }
    try:
        # 根据 product_id 获取对应产品配置
        nacos_config = GetYamlConfig().get_config("Nacos").get(product_id)
        assert nacos_config, f"获取 {product_id} 产品的 nacos 配置信息失败，检查 config.yaml 配置文件。"

        # 根据 environment 获取对应 namespace
        if environment == "PROD":
            namespace = nacos_config.get("prod_namespace")
        else:
            namespace = nacos_config.get("uat_namespace")
        namespace = nacos_config.get("test_namespace")
        group = "DEFAULT_GROUP"

        # 转换 nacos_info 数据
        nacos_keys = format_nacos_info(nacos_info)

        # 创建客户端
        nacos_client = NacosClient(nacos_config)

        # 校验操作，校验不通过直接抛异常，不执行变更
        for data_id, keys in nacos_keys.items():
            # 从nacos获取配置
            confit_text = nacos_client.get_config(namespace=namespace, group=group, data_id=data_id)
            # 把从nacos获取到的配置 由文本 转换为 dict类型
            config_dict = nacos_client.convert_text_to_dict(confit_text)
            # 检查要操作的key与对的action是否合规(有该key才可以删除和修改，无该key才可以新增)
            check_keys_message = nacos_client.check_all_keys(config_dict, keys)
            if check_keys_message:
                # for key, message in check_keys_message.items():
                #     d_logger.info(data_id, key, message)
                raise KeyError("Nacos 配置文件 keys 校验不通过，不进行变更动作，检查配置信息。")
            else:
                pass
        d_logger.info("Nacos 配置文件 keys 全部校验通过")

        # # 校验通过，开始实际变更操作
        # for data_id, keys in nacos_keys.items():
        #     # 从nacos获取配置
        #     confit_text = nacos_client.get_config(namespace=namespace, group=group, data_id=data_id)
        #     # 把从nacos获取到的配置 由文本 转换为 dict类型
        #     config_dict = nacos_client.convert_text_to_dict(confit_text)
        #     d_logger.info(f"记录变更前 nacos 配置信息, data_id：{data_id}, 配置内容：{config_dict}")
        #     new_config = nacos_client.update_config(config_dict, keys)
        #     content = nacos_client.convert_dict_to_text(new_config)
        #     message = nacos_client.post_config(namespace=namespace, group=group, data_id=data_id, content=content)
        #     d_logger.info(f"变更 nacos 配置返回信息：{message}")

        # Nacos 变更全部执行成功，返回 True
        return_data["status"] = True
        return_data["msg"] = f"产品 {product_id} Nacos 变更配置成功。"
    except KeyError as err:
        return_data["msg"] = traceback.format_exc()
    except Exception as err:
        return_data["msg"] = f"产品 {product_id} Nacos 变更配置执行异常，异常原因：{traceback.format_exc()}"
    return return_data

# 格式化代码数据
def format_code_info(
        code_info: str = None,
        environment: str = "UAT"
) -> List:
    code_info_list = []
    if code_info:
        # 处理 code_info 数据，转为列表数据
        tmp_dict = dict()
        for i in code_info.split("\r\n"):
            tmp_info = i.split("@@")
            tmp_dict["project_name"] = tmp_info[0]
            tmp_dict["code_version"] = tmp_info[1]
            tmp_dict["tag"] = tmp_info[2]
            tmp_dict["environment"] = environment
            code_info_list.append(tmp_dict)
    return code_info_list

# 对比两个列表差异值
def compare_list_info(
        last_list_info: List,
        current_list_info: List
) -> List[Dict[str, Union[str, int]]]:
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
def completed_workflow_notice(
        start_time: str,
        end_time: str,
        email_summary: str,
        upgrade_info_list: List
) -> Dict:
    upgrade_content: str = "\n".join(upgrade_info_list) if None not in upgrade_info_list else "无代码升级，SQL 或配置已升级到 UAT 环境"
    send_msg: str = f"""Dear All:

1. Upgrade start time:  {start_time}
2. Upgrade end   time:  {end_time}
3. Upgrader: API
4. The following content has been upgraded:

{upgrade_content}
"""
    send_result = email_obj.send_email(send_msg, email_summary)
    return send_result

# 多线程方式升级代码
def thread_code_handle(
        wait_upgrade_list: List,
        upgrade_success_list: List,
        upgrade_info_list: List
    ) -> Tuple[List, List]:
    # 获取 CMDB 配置信息
    cmdb_config = GetYamlConfig().get_config("CMDB")
    assert cmdb_config, f"获取 CMDB 配置信息失败，检查 config.yaml 配置文件。"
    cmdb_host = cmdb_config.get('host')
    cmdb_token = cmdb_config.get('token')

    # 创建 CMDB 对象
    cmdb_obj = CmdbAPI(
        host=cmdb_host,
        token=cmdb_token
    )

    # 延迟升级，等待 harbor 镜像同步到 gcp
    if len(wait_upgrade_list) <= 3:
        sleep(30)
    elif 3 < len(wait_upgrade_list) <= 6:
        sleep(75)
    else:
        sleep(90)
    with ThreadPoolExecutor(max_workers=12) as executor:
        # 循环待升级代码列表，调用 CMDB 对象 project_deploy 方法升级代码
        futures = []
        for wait_upgrade_ins in wait_upgrade_list:
            # d_logger.info(wait_upgrade_ins)
            future = executor.submit(cmdb_obj.project_deploy, **wait_upgrade_ins)
            futures.append(future)

        # 循环升级结果列表，根据列表状态返回升级结果
        upgrade_result_list = [future.result() for future in futures]
        for upgrade_result in upgrade_result_list:
            upgrade_data = upgrade_result['data']
            # 升级成功记录数据
            if upgrade_result["status"]:
                # 升级成功的数据放入 upgrade_success_list
                upgrade_success_list.append(upgrade_data)
                upgrade_info_list.append(f"{upgrade_data['project_name']:25s} 升级版本: {upgrade_data['code_version']}")
                # 日志记录升级消息
                d_logger.info(upgrade_result["msg"])
            # 多进程方式升级失败，继续尝试2次升级重试
            else:
                # 日志记录升级错误消息
                d_logger.error(upgrade_result["msg"])
                # # CodeUpgradeFailed 重试机制，等待10s重试2次升级
                # retry_flag = 0
                # while retry_flag < 2:
                #     sleep(10)
                #     retry_result = cmdb_obj.project_deploy(**upgrade_data)
                #     if retry_result["status"]:
                #         upgrade_success_list.append(upgrade_data)
                #         upgrade_info_list.append(f"{upgrade_data['project_name']:25s} 升级版本: {upgrade_data['code_version']}")
                #         d_logger.info(retry_result["msg"])
                #         break
                #     retry_flag += 1
        return upgrade_success_list, upgrade_info_list

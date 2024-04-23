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
) -> Dict:
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
            # 提交 Archery SQL 工单，提交成功保存入 SqlWorkflow 表
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
            # TODO: 提交 Archery SQL 备份工单

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
        workflow_name: str = "",
        sql_info: str = None,
        environment: str = "UAT",
) -> Dict:
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

        # 根据 environment 获取对应 Archery 配置
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
        # sqlworkflow_ser_obj = SqlWorkflowSerializer()

        # TODO: 判断是否存在需要备份工单，先执行备份工单再执行后续 SQL. 获取 SqlWorkflow 表中所有待审核状态的备份工单?

        # 开始执行 SQL 逻辑，循环 sql_info 中每个 SQL 工单数据
        for sql_data in real_sql_info_list:
            file_name = sql_data("file_name")
            commit_sha = sql_data("commit_sha")
            # 获取工单实例以及工单 ID
            sqlworkflow_ins = sqlworkflow_obj.objects.get(
                workflow_name=workflow_name,
                sql_file_name=file_name,
                sql_release_info=commit_sha
            )
            w_id = sqlworkflow_ins.w_id
            # 查询 Archery 上当前状态，根据状态对应处理
            select_result = archery_obj.get_workflows(w_id=w_id)
            assert select_result["status"], "查询 Archery 工单状态失败，检查日志"
            select_workflow_status = select_result['data'][0]["status"]

            # workflow_manreviewing：执行自动审核
            if select_workflow_status == "workflow_manreviewing":
                audit_result = archery_obj.audit_workflow(workflow_id=w_id)
                assert audit_result["status"], f"工单 {workflow_name} SQL 自动审核失败，返回结果：{audit_result}"
                d_logger.info(f"工单 {workflow_name} SQL 自动审核成功，SQL 文件：{file_name}，版本：{commit_sha}")
                select_workflow_status = "workflow_review_pass"
            # workflow_review_pass：执行自动执行
            elif select_workflow_status == "workflow_review_pass":
                execute_result = archery_obj.execute_workflow(workflow_id=w_id)
                sleep(15)
                assert execute_result["status"], f"工单 {workflow_name} SQL 自动执行失败，返回结果：{execute_result}"
                d_logger.info(f"工单 {workflow_name} SQL 自动执行成功，SQL 文件：{file_name}，版本：{commit_sha}")
                select_workflow_status = "workflow_finish"
            # workflow_finish：跳过
            elif select_workflow_status == "workflow_finish":
                # d_logger.info(f"工单 {workflow_name} SQL 状态为 workflow_finish，SQL 文件：{file_name}，版本：{commit_sha}")
                pass
            # workflow_queuing / workflow_exception：中止流程
            else:
                # d_logger.error(f"工单 {workflow_name} SQL 状态为异常状态 {select_workflow_status}，SQL 文件：{file_name}，版本：{commit_sha}")
                raise Exception("工单状态非正常状态，中止 SQL 执行流程，检查日志")
            # 保存工单状态到 SqlWorkflow 表中
            sqlworkflow_ins.w_status = select_workflow_status
            sqlworkflow_ins.save()

            # TODO: 获取提交 Archery SQL 备份工单数据

        workflow_finish_number = 0
        for sql_data in real_sql_info_list:
            file_name = sql_data("file_name")
            commit_sha = sql_data("commit_sha")
            finish_flag = sqlworkflow_obj.objects.filter(
                workflow_name=workflow_name,
                sql_file_name=file_name,
                sql_release_info=commit_sha
            ).filter(w_status="workflow_finish")
            if finish_flag:
                workflow_finish_number += 1
        # 当前工单所有 SQL 文件自动审核和自动执行成功
        if len(real_sql_info_list) == workflow_finish_number:
            return_data["status"] = True
            return_data["msg"] = "SQL 自动审核与自动执行成功"
        # 存在 SQL 自动审核或自动执行失败
        else:
            return_data["msg"] = "SQL 自动审核或自动执行失败，检查日志"
    except Exception as err:
        return_data["msg"] = f"SQL 自动审核或自动执行异常，异常原因：{traceback.format_exc()}"
    return return_data

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
        for i in code_info.split("\r\n"):
            tmp_dict = dict()
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

from typing import Dict, List, Union, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict, UserDict
from time import sleep
import re

from utils.cmdb_api import CmdbAPI
from utils.getconfig import GetYamlConfig
from utils.nacos_client import NacosClient
from utils.svn_client import SvnClient
from utils.pgsql_api import PostgresClient
from utils.email_client import EmailClient
email_obj = EmailClient()
import logging
d_logger = logging.getLogger("default_logger")

__all__ = [
    # sql
    "get_sql_commit_data",
    "get_backup_commit_data",
    # nacos
    "format_nacos_info",
    "nacos_handle",
    # code
    "format_code_info",
    "compare_list_info",
    "completed_workflow_notice",
    "thread_code_upgrade"
]

# 传入 Jira 表单中 sql 升级数据，返回 commit_data 和 bk_commit_data 数据，用于提交 Archery
def get_sql_commit_data(
        sql_data: Dict[str, Union[str, int]],
        sql_info: List,
        summary: str
) -> Tuple[Union[None, Dict], Union[None, Dict]]:

    # 获取 sql 文件 svn 相关参数
    svn_path = sql_data.get("svn_path")
    svn_version = sql_data.get("svn_version")
    svn_file = sql_data.get("svn_file")

    # 根据 has_deploy_uat 字段值判断是否需要提交 SQL
    has_deploy_uat_flag = sql_data.get("has_deploy_uat")
    if not has_deploy_uat_flag:
        # 通过 svn 信息获取每个sql 文件与内容，根据内容提交sql工单
        svn_obj = SvnClient(svn_path)
        sql_content = svn_obj.get_file_content(revision=svn_version, filename=svn_file)

        # # 增加审核功能，sql_content_value 工单内容不允许 create 语句设置 timestamp 属性，需要为 timestamp(0)
        # audit_timestamp = re.findall(" timestamp[,\s]", sql_content_value)
        # assert not audit_timestamp, "工单内容存在 timestamp 属性定义，不提交工单，检查 sql 内容。"

        # 生成提交 Archery 工单数据主逻辑
        # 提交 sql 序号，按顺序执行 sql
        seq_index = sql_info.index(sql_data) + 1
        # DB 所属资源组名称：QC | ISLOT | ISAGENT
        db_name = None
        # yakir_test
        if "yakir" in svn_file:
            sql_resource_name = "QC"
            sql_instance_name = "uat-pg-env"
            table_catalog = "dbtest"
            bk_sql_content_value = get_backup_commit_data(table_catalog, sql_content)
            bk_commit_data = {
                "sql_index": str(seq_index),
                'sql_release_info': str(svn_version),
                "sql": bk_sql_content_value,
                "workflow_name": f"{summary}_备份工单",
                "resource_tag": sql_resource_name,
                "instance_tag": sql_instance_name
            } if bk_sql_content_value else None
        # QC
        elif "qc" in svn_path:
            qc_ins_map = {
                "rex_merchant_qc": "qc-merchant",
                "rex_admin": "qc-admin",
                "rex_rpt": "qc-report",
                "rex_merchant_b01": "b01-merchant",
                "rex_merchant_rs8": "rs8-merchant",
                "rex_merchant_fpb": "fpb-merchant",
                "rex_merchant_psl": "psl-merchant"
            }
            # sql_resource_name = re.split(r"[/_]\s*", svn_path.upper())[2]
            sql_resource_name = "QC"
            # 取出数据库实例名称
            svn_path_value_list = svn_path.split("/")
            svn_path_value_list = [k for k in svn_path_value_list if k != ""]
            sql_instance_name = qc_ins_map[svn_path_value_list[-1]]
            # 备份库 SQL 信息获取
            # bk_sql_content_value = get_backup_commit_data(sql_instance_name, sql_content_value)
            # bk_commit_data = {
            #     "sql_index": str(seq_index),
            #     'sql_release_info': str(svn_version),
            #     "sql": bk_sql_content_value,
            #     "workflow_name": f"{current_summary}_备份工单",
            #     "resource_tag": sql_resource_name,
            #     "instance_tag": sql_instance_name
            # } if bk_sql_content_value else None
            bk_commit_data = None
        # ISLOT
        elif "islot" in svn_path:
            sql_resource_name = svn_path.split("/")[1].upper()
            sql_instance_name = "islot-uat"
            db_name = "ilum01"
            if "liveslot-sql-hotfix" in svn_path:
                db_name = "hotfix"
            elif "liveslot-sql-v2" in svn_path:
                db_name = "hotfix"
            elif "liveslot-sql-v3" in svn_path:
                db_name = "ilum03"
            elif "liveslot-sql-v4" in svn_path:
                db_name = "ilum05"
            elif "pachinko-sql" in svn_path:
                sql_instance_name = "pachinko-uat"
                db_name = "ilum02"
            bk_commit_data = None
        # ISAGENT
        elif "isagent" in svn_path:
            sql_resource_name = "ISAGENT"
            if "isagent-merchant" in svn_path:
                sql_instance_name = "isagent-merchant"
                db_name = "ilup01"
            elif "isagent-admin" in svn_path:
                sql_instance_name = "isagent-admin"
                db_name = "ilup02"
            elif "isagent-report" in svn_path:
                sql_instance_name = "isagent-report"
                db_name = "ilup03"
            elif "ipachinko-merchant" in svn_path:
                sql_instance_name = "ipachinko-merchant"
                db_name = "ilup04"
            elif "is03-cashsite" in svn_path:
                sql_instance_name = "is03-cashsite"
                db_name = "ilup05"
            elif "bw01-cashsite" in svn_path:
                sql_instance_name = "bw01-cashsite"
                db_name = "ilup06"
            bk_commit_data = None
            # d_logger.info("debug" + sql_resource_name)
        else:
            error_msg = "svn 路径不包含产品关键字路径，请确认是否正确输入 svn 路径。"
            d_logger.error(f"{error_msg}")
            raise ValueError(f"{error_msg}")
        commit_data = {
            "sql_index": str(seq_index),
            'sql_release_info': str(svn_version),
            "sql_content": sql_content,
            "workflow_name": summary,
            "resource_tag": sql_resource_name,
            "instance_tag": sql_instance_name,
            "db_name": db_name
        }
        return commit_data, bk_commit_data
    else:
        d_logger.info(f"{svn_path} 下 SQL: {svn_file} 已在 UAT 环境执行，版本号: {svn_version}")
        return None, None

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


# 转化 nacos 数据
def format_nacos_info(
        nacos_info: str = None
) -> Dict:
    data = {}
    if nacos_info:
        for i in nacos_info.split("\r\n"):
            columns = i.split("@@")
            data_id = columns[0]
            item = {
                "action": columns[1],
                "key": columns[2],
                "value": columns[3],
            }
            if data_id in data:
                data[data_id].append(item)
            else:
                data[data_id] = []
    return data


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
        nacos_config = GetYamlConfig().get_config("NACOS").get(product_id)
        assert nacos_config, f"获取 {product_id} 产品的 nacos 配置信息失败，检查 config.yaml 配置文件。"

        # 根据 environment 获取对应 namespace
        # if environment == "PROD":
        #     namespace = nacos_config.get("prod_namespace")
        # else:
        #     namespace = nacos_config.get("uat_namespace")
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
                d_logger.info("Nacos 变更配置文件 keys 校验通过")

        # 校验通过，开始实际变更操作
        for data_id, keys in nacos_keys.items():
            # 从nacos获取配置
            confit_text = nacos_client.get_config(namespace=namespace, group=group, data_id=data_id)
            # 把从nacos获取到的配置 由文本 转换为 dict类型
            config_dict = nacos_client.convert_text_to_dict(confit_text)
            d_logger.info(f"记录变更前 nacos 配置信息, data_id：{data_id}, 配置内容：{config_dict}")
            new_config = nacos_client.update_config(config_dict, keys)
            content = nacos_client.convert_dict_to_text(new_config)
            message = nacos_client.post_config(namespace=namespace, group=group, data_id=data_id, content=content)
            d_logger.info(f"变更 nacos 配置返回信息：{message}")
    except KeyError as err:
        return_data["msg"] = err.__str__()
    except Exception as err:
        return_data["msg"] = f"处理 Nacos 变更动作异常，异常原因：{err.__str__()}"
    return return_data


# 转化升级代码数据
def format_code_info(
        code_info: str = None,
        env: str = "UAT"
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
            tmp_dict["env"] = env
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
def thread_code_upgrade(
        wait_upgrade_list: List,
        upgrade_success_list: List,
        upgrade_info_list: List
    ) -> Tuple[List, List]:
    # 创建 CMDB 对象
    cmdb_obj = CmdbAPI()

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
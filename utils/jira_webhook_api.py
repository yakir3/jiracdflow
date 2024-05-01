from typing import Dict, Union, Any
from datetime import datetime
import traceback

from utils.jira_api import JiraWebhookData, JiraAPI
from utils.cicdflow_utils import *
import logging
d_logger = logging.getLogger("default_logger")

__all__ = [
    "JiraEventWebhookAPI"
]

# JIRA 实例，用于获取 issue 状态以及转换状态
jira_obj = JiraAPI()

class JiraEventWebhookAPI(JiraWebhookData):
    def __init__(self, request_data: Dict):
        super().__init__(request_data)
        # Jira webhook 当前的表单数据用父类转换为 JiraIssueSerializer 格式数据
        self.webhook_data = self.get_custom_issue_data().get('data')
        # 取出 webhook_data 中 changelog 与 event 字段（created 或 updated）
        self.webhook_from = self.webhook_data.pop("fromstring")
        self.webhook_to = self.webhook_data.pop("tostring")
        self.webhook_event = self.webhook_data.pop("webhook_event")
        # 获取 environment 字段
        self.webhook_environment = self.webhook_data.get("environment")
        # cdflow 执行每个流程返回数据格式
        self.webhook_return_data = {
            "status": False,
            "msg": "",
            'data': dict()
        }

    def created_event_action(
            self,
            current_issue_data: Dict,
    ) -> Dict[str, Union[bool, str, Dict]]:
        """
        webhook event 值为 jira:issue_created。判断是否有 SQL，并转换进行下一状态
        """
        try:
            current_issue_key = current_issue_data["issue_key"]
            current_summary = current_issue_data["summary"]
            current_sql_info = current_issue_data["sql_info"]

            # 临时操作，人工审核流程
            self.webhook_return_data["status"] = True
            self.webhook_return_data["msg"] = f"工单 {current_summary} 由 <REVIEW PENDING> 状态创建，忽略触发动作，等待人工审核"

            #  无 SQL 升级，执行流程转换状态到 <CONFIG PROCESSING>
            # if not current_sql_info:
            #     self.webhook_return_data["msg"] = f"Jira 工单：{current_summary} 已被创建，工单无 SQL 升级数据，转换到状态 <CONFIG PROCESSING>"
            #     jira_obj.change_transition(current_issue_key, "NoSqlUpgrade")
            #  有 SQL 升级，执行流程转换状态到 <SQL PENDING>
            # else:
            #     self.webhook_return_data["msg"] = f"Jira 工单：{current_summary} 已被创建，工单有 SQL 升级数据，触发转换 TriggerSubmitSql"
            #     jira_obj.change_transition(current_issue_key, "TriggerSubmitSql")
            # self.webhook_return_data["status"] = True
        except Exception as err:
            self.webhook_return_data["msg"] = err.__str__()
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_sql_pending(
            self,
            last_issue_obj: Any,
            current_issue_data: Dict
    ) -> Dict[str, Union[bool, str, Dict]]:
        # 更新 JiraIssue 表数据
        last_issue_obj.init_flag["sql_init_flag"] += 1
        last_issue_obj.issue_status = "SQL PENDING"
        last_issue_obj.save()

        # 获取工单数据信息
        current_issue_key = current_issue_data["issue_key"]
        current_sql_info = current_issue_data["sql_info"]
        current_summary = current_issue_data["summary"]
        current_environment = current_issue_data["environment"]

        try:
            # sql_info 数据为空，直接触发到下一流程
            if not bool(current_sql_info):
                jira_obj.change_transition(current_issue_key, "NoSqlUpgrade")
                self.webhook_return_data["status"] = True
                self.webhook_return_data["msg"] = f"无 SQL 升级，升级工单 {current_summary} 触发转换 <NoSqlUpgrade> 到状态 <CONFIG PROCESSING>"
                return self.webhook_return_data

            # 格式化 sql_info 数据
            sql_info_list = format_sql_info(current_sql_info)

            # sql_info 数据不为空，调用 sql_submit_handle 方法提交 SQL
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 开始提交 SQL，开始时间：{start_time}")
            sql_submit_res = sql_submit_handle(
                sql_info_list=sql_info_list,
                workflow_name=current_summary,
                environment=current_environment
            )
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 提交 SQL 结束，结束时间：{end_time}")

            # sql 提交成功，流程转换状态到下一步
            if sql_submit_res["status"]:
                jira_obj.change_transition(current_issue_key, "SubmitSqlSuccessful")
                self.webhook_return_data["status"] = True
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} SQL 提交 Archery 成功，转换到状态 <SQL PROCESSING>"
            # sql 提交失败，流程转换状态 FIX PENDING
            else:
                jira_obj.change_transition(current_issue_key, "SubmitSqlFailed")
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} SQL 提交 Archery 失败，转换到状态 <FIX PENDING>"
                self.webhook_return_data["data"] = sql_submit_res
        except Exception:
            self.webhook_return_data["msg"] = f"升级工单 {current_summary} <SQL PENDING> webhook 触发失败，异常原因：{traceback.format_exc()}"
            jira_obj.change_transition(current_issue_key, "SubmitSqlFailed")
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_sql_processing(
            self,
            last_issue_obj: Any,
            current_issue_data: Dict
    ) -> Dict[str, Union[bool, str, Dict]]:
        # 更新 JiraIssue 表数据
        # last_issue_obj.init_flag["sql_init_flag"] += 1
        last_issue_obj.issue_status = "SQL PROCESSING"
        last_issue_obj.save()

        # 获取工单数据信息
        current_issue_key = current_issue_data["issue_key"]
        current_sql_info = current_issue_data["sql_info"]
        current_summary = current_issue_data["summary"]
        current_environment = current_issue_data["environment"]

        try:
            # 格式化 sql_info 数据
            sql_info_list = format_sql_info(current_sql_info)

            # 升级 SQL 主逻辑
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 开始执行 SQL，开始时间：{start_time}")
            # 调用 sql_upgrade_handle 函数执行配置自动变更
            sql_upgrade_res = sql_upgrade_handle(
                sql_info_list=sql_info_list,
                workflow_name=current_summary,
                environment=current_environment
            )
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 执行 SQL 结束，结束时间：{end_time}")

            # sql 升级成功，流程转换到下一步
            if sql_upgrade_res["status"]:
                jira_obj.change_transition(current_issue_key, "SqlUpgradeSuccessful")
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} SQL 升级成功，转换到状态 <CONFIG PROCESSING>"
            # sql 升级失败，流程转换 FIX PENDING
            else:
                jira_obj.change_transition(current_issue_key, "SqlUpgradeFailed")
                self.webhook_return_data["status"] = False
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} SQL 升级失败，转换到状态 <FIX PENDING>"
        except Exception:
            self.webhook_return_data["msg"] = f"升级工单 {current_summary} <SQL PROCESSING> webhook 触发失败，异常原因：{traceback.format_exc()}"
            jira_obj.change_transition(current_issue_key, "SqlUpgradeFailed")
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_config_processing(
            self,
            last_issue_obj: Any,
            current_issue_data: Dict
    ) -> Dict[str, Union[bool, str, Dict]]:
        """
        <CONFIG PROCESSING> 状态，处理配置文件变更动作
        """
        # 更新 JiraIssue 表数据
        # last_issue_obj.init_flag["nacos_init_flag"] += 1
        last_issue_obj.issue_status = "CONFIG PROCESSING"
        last_issue_obj.save()

        # 获取 nacos_info 数据信息
        # last_nacos_info = last_issue_obj.nacos_info
        current_issue_key = current_issue_data["issue_key"]
        current_nacos_info = current_issue_data["nacos_info"]
        current_summary = current_issue_data["summary"]
        current_product_id = current_issue_data["product_id"]
        current_environment = current_issue_data["environment"]

        try:
            # nacos_info 数据为空，直接触发到下一流程
            if not bool(current_nacos_info):
                jira_obj.change_transition(current_issue_key, "NoConfigUpgrade")
                self.webhook_return_data["status"] = True
                self.webhook_return_data["msg"] = f"无配置升级，升级工单 {current_summary} 转换到状态 <CODE PROCESSING>"
                return self.webhook_return_data

            # 格式化 nacos_info 数据
            nacos_info_dict = format_nacos_info(current_nacos_info)

            # nacos_info 数据不为空，调用 nacos_handle 方法执行配置自动变更
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 开始配置变更，开始时间：{start_time}")
            nacos_res = nacos_handle(
                nacos_info_dict=nacos_info_dict,
                product_id=current_product_id,
                environment=current_environment
            )
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 配置变更结束，结束时间：{end_time}")

            # nacos 配置变更成功，执行流程转换状态到下一步
            if nacos_res["status"]:
                jira_obj.change_transition(current_issue_key, "ConfigUpgradeSuccessful")
                self.webhook_return_data["status"] = True
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} Nacos 配置变更执行成功，转换到状态 <CODE PROCESSING>"
            # nacos 配置变更失败，流程跳转 FIX PENDING
            else:
                jira_obj.change_transition(current_issue_key, "ConfigUpgradeFailed")
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} Nacos 配置变更执行失败，返回：{nacos_res}"
        except Exception:
            self.webhook_return_data["msg"] = f"升级工单 {current_summary} <CONFIG PROCESSING> webhook 触发失败，异常原因：{traceback.format_exc()}"
            jira_obj.change_transition(current_issue_key, "ConfigUpgradeFailed")
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_code_processing(
            self,
            last_issue_obj: Any,
            current_issue_data: Dict
    ) -> Dict[str, Union[bool, str, Dict]]:
        """
        <CODE PROCESSING> 状态，处理代码升级动作
        """
        # 更新 JiraIssue 表数据
        last_issue_obj.issue_status = "CODE PROCESSING"
        last_issue_obj.save()

        # 获取工单数据信息
        last_code_info = last_issue_obj.code_info
        last_code_init_flag = last_issue_obj.init_flag["code_init_flag"]
        current_issue_key = current_issue_data["issue_key"]
        current_code_info = current_issue_data["code_info"]
        current_summary = current_issue_data["summary"]
        current_product_id = current_issue_data["product_id"]
        current_environment = current_issue_data["environment"]

        try:
            # code_info 数据为空，直接触发到下一流程
            if not bool(current_code_info):
                last_issue_obj.issue_status = "UPGRADED DONE"
                last_issue_obj.save()
                jira_obj.change_transition(current_issue_key, "NoCodeUpgrade")
                self.webhook_return_data["status"] = True
                self.webhook_return_data["msg"] = f"无代码需要升级，升级工单 {current_summary} 转换到状态 <UPGRADED DONE>"
                return self.webhook_return_data

            # 格式化 code_info 数据
            last_code_info_list = format_code_info(last_code_info, current_environment)
            current_code_info_list = format_code_info(current_code_info, current_environment)

            # code_info 数据不为空
            # 首次升级，直接使用数据库中的 code_info 进行升级
            if not last_code_init_flag:
                wait_upgrade_list = format_code_info(current_code_info, current_environment)
            # 迭代升级，对比数据库中的 code_info 与当前 Jira 工单中的 code_info 差异部分
            else:
                wait_upgrade_list = compare_list_info(last_code_info_list, current_code_info_list)
                assert wait_upgrade_list, "数据库中 code_info 与当前 Jira 工单 code_info 数据无差异部分，转换到状态 <UPGRADE DONE>"

            # 调用 thread_code_handle 方法执行多线程升级代码
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 开始升级代码，开始时间：{start_time}")
            code_res = thread_code_handle(
                last_code_init_flag=last_code_init_flag,
                current_code_info=current_code_info,
                product_id=current_product_id,
                environment=current_environment,
                issue_key=current_issue_key,
                wait_upgrade_list=wait_upgrade_list,
                last_code_info_list=last_code_info_list
            )
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 代码升级结束，结束时间：{end_time}")

            #  代码升级成功，执行流程转换状态到下一步
            if code_res["status"]:
                jira_obj.change_transition(current_issue_key, "CodeUpgradeSuccessful")
                self.webhook_return_data["status"] = True
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} 代码升级成功，转换到状态 <UPGRADE DONE>"
                # TODO: 升级成功邮件通知
                # d_logger.info(completed_workflow_notice(start_time, end_time, current_summary, upgrade_info_list))
            # 代码升级失败，流程跳转 FIX PENDING
            else:
                jira_obj.change_transition(current_issue_key, "CodeUpgradeFailed")
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} 代码升级失败，返回结果：{code_res}"
        except AssertionError as err:
            self.webhook_return_data["status"] = True
            self.webhook_return_data["msg"] = err.__str__()
            jira_obj.change_transition(current_issue_key, "CodeUpgradeSuccessful")
        except Exception:
            self.webhook_return_data["msg"] = f"升级工单 {current_summary} <CODE PROCESSING> webhook 触发失败，异常原因：{traceback.format_exc()}"
            jira_obj.change_transition(current_issue_key, "CodeUpgradeFailed")
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_fix_pending(
            self,
            last_issue_obj: Any
    ) -> Dict[str, Union[bool, str, Dict]]:
        last_issue_obj.issue_status = "FIX PENDING"
        last_issue_obj.save()
        summary = last_issue_obj.summary

        try:
            self.webhook_return_data["status"] = True
            self.webhook_return_data["msg"] = f"工单 {summary} <FIX PENDING> 状态 webhook 触发成功，等待人工修复数据"
        except Exception as err:
            self.webhook_return_data["msg"] = f"工单 {summary} <FIX PENDING> 状态 webhook 触发失败，异常原因：{err.__str__()}"
        # self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

from typing import Dict, List, Union, Any, Tuple
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
        # Jira webhook 当前的表单数据用父类转换为 serializer 格式数据
        self.webhook_data = self.get_custom_issue_data().get('data')
        # 取出 webhook_data 中 changelog 与 event 字段（created 或 updated）
        self.webhook_from = self.webhook_data.pop("fromstring")
        self.webhook_to = self.webhook_data.pop("tostring")
        self.webhook_event = self.webhook_data.pop("webhook_event")
        # 获取 environment 字段
        self.webhook_environment = self.webhook_data.get("environment")
        # cdflow 执行每个流程返回数据格式
        self.webhook_return_data = {
            "status": True,
            "msg": "",
            'data': dict()
        }

    def created_event_action(
            self, 
            current_issue_data: Dict, 
    ) -> Dict[str, Union[str, dict]]:
        """
        webhook 事件为 created 时，Jira 工单初始化创建。判断是否有 SQL，并转换进行下一状态
        """
        try:
            current_issue_key = current_issue_data["issue_key"]
            current_summary = current_issue_data["summary"]
            current_sql_info = current_issue_data["sql_info"]

            self.webhook_return_data["msg"] = f"REVIEW PENDING 状态创建的工单 {current_summary}，忽略触发动作，等待人工审核"
            # # 判断是否有 SQL 升级数据：触发进入下一步流程
            # if not current_sql_info:
            #     self.webhook_return_data["msg"] = f"Jira工单被创建，工单名：{current_summary}，工单无SQL升级数据，转换到状态 <CONFIG PROCESSING>"
            #     jira_obj.change_transition(current_issue_key, "NoSqlUpgrade")
            # else:
            #     self.webhook_return_data["msg"] = f"Jira工单被创建，工单名：{current_summary}，工单有SQL升级数据，转换到状态 <SQL PENDING>"
            #     jira_obj.change_transition(current_issue_key, "TriggerSubmitSql")
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = err.__str__()
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_sql_pending(
            self,
            last_issue_obj: Any,
            current_issue_data: Dict
    ) -> Dict:
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
                self.webhook_return_data["msg"] = f"无 SQL 升级，升级工单 {current_summary} 触发转换 <NoSqlUpgrade> 到状态 <CONFIG PROCESSING>"
                return self.webhook_return_data

            # sql_info 数据不为空，调用 sql_submit_handle 函数提交 SQL
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 开始提交 SQL，开始时间：{start_time}")
            sql_submit_res = sql_submit_handle(
                workflow_name=current_summary,
                sql_info=current_sql_info,
                environment=current_environment
            )
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 提交 SQL 结束，结束时间：{end_time}")


            # sql 提交成功，流程转换状态到下一步
            if sql_submit_res["status"]:
                jira_obj.change_transition(current_issue_key, "SubmitSqlSuccessful")
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} SQL 提交成功，转换到状态 <SQL PROCESSING>"
            # sql 提交失败，流程转换状态 FIX PENDING
            else:
                jira_obj.change_transition(current_issue_key, "SubmitSqlFailed")
                self.webhook_return_data["status"] = False
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} SQL 提交失败，转换到状态 <FIX PENDING>"
                self.webhook_return_data["data"] = sql_submit_res
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = f"升级工单 {current_summary} <SQL PENDING> webhook 触发失败，异常原因：{traceback.format_exc()}"
            jira_obj.change_transition(current_issue_key, "SubmitSqlFailed")
        return self.webhook_return_data

    def updated_event_sql_processing(
            self,
            last_issue_obj: Any,
            current_issue_data: Dict
    ) -> Dict:
        # 更新 JiraIssue 表数据
        last_issue_obj.init_flag["sql_init_flag"] += 1
        last_issue_obj.issue_status = "SQL PROCESSING"
        last_issue_obj.save()

        # 获取工单数据信息
        current_issue_key = current_issue_data["issue_key"]
        current_sql_info = current_issue_data["sql_info"]
        current_summary = current_issue_data["summary"]
        current_environment = current_issue_data["environment"]

        try:
            self.webhook_return_data["msg"] = "SQL PROCESSING 状态，功能待上线，忽略触发动作"
            # # 升级 SQL 主逻辑
            # start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # d_logger.info(f"工单 {current_summary} 开始执行 SQL，开始时间：{start_time}")
            # # 调用 sql_upgrade_handle 函数执行配置自动变更
            # sql_upgrade_res = sql_upgrade_handle(
            #     workflow_name=current_summary,
            #     sql_info=current_sql_info,
            #     environment=current_environment
            # )
            # end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # d_logger.info(f"工单 {current_summary} 执行 SQL 结束，结束时间：{end_time}")
            #
            # # sql 升级成功，流程转换到下一步
            # if sql_upgrade_res["status"]:
            #     jira_obj.change_transition(current_issue_key, "SqlUpgradeSuccessful")
            #     self.webhook_return_data["msg"] = f"升级工单 {current_summary} SQL 升级成功，转换到状态 <CONFIG PROCESSING>"
            # # sql 升级失败，流程转换 FIX PENDING
            # else:
            #     jira_obj.change_transition(current_issue_key, "SqlUpgradeFailed")
            #     self.webhook_return_data["status"] = False
            #     self.webhook_return_data["msg"] = f"升级工单 {current_summary} SQL 升级失败，转换到状态 <FIX PENDING>"
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = f"升级工单 {current_summary} <SQL PROCESSING> webhook 触发失败，异常原因：{traceback.format_exc()}"
            jira_obj.change_transition(current_issue_key, "SqlUpgradeFailed")
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_config_processing(
            self,
            last_issue_obj: Any,
            current_issue_data: Dict
    ):
        """
        <CONFIG PROCESSING> 状态，处理配置文件变更动作
        """
        # 更新 JiraIssue 表数据
        last_issue_obj.init_flag["nacos_init_flag"] += 1
        last_issue_obj.init_flag["config_init_flag"] += 1
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
                self.webhook_return_data["msg"] = f"无配置升级，升级工单 {current_summary} 转换到状态 <CODE PROCESSING>"
            else:
                self.webhook_return_data["msg"] = f"有配置升级，等待人工处理。升级工单 {current_summary} 状态不变"

            # # nacos_info 数据不为空，调用 nacos_handle 函数执行配置自动变更
            # start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # d_logger.info(f"工单 {current_summary} 开始配置变更，开始时间：{start_time}")
            # nacos_res = nacos_handle(
            #     nacos_info=current_nacos_info,
            #     product_id=current_product_id,
            #     environment=current_environment
            # )
            # end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # d_logger.info(f"工单 {current_summary} 配置变更结束，结束时间：{end_time}")
            #
            # # nacos 变更执行成功，执行流程转换状态到下一步
            # if nacos_res["status"]:
            #     jira_obj.change_transition(current_issue_key, "ConfigUpgradeSuccessful")
            #     self.webhook_return_data["msg"] = f"升级工单 {current_summary} Nacos 配置变更执行成功，转换到状态 <CODE PROCESSING>"
            # # 变更执行失败，流程跳转 FIX PENDING
            # else:
            #     jira_obj.change_transition(current_issue_key, "ConfigUpgradeFailed")
            #     self.webhook_return_data["status"] = False
            #     self.webhook_return_data["msg"] = f"升级工单 {current_summary} Nacos 配置变更执行失败，返回：{nacos_res}"
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = f"升级工单 {current_summary} <CONFIG PROCESSING> webhook 触发失败，异常原因：{traceback.format_exc()}"
            jira_obj.change_transition(current_issue_key, "ConfigUpgradeFailed")
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_code_processing(
            self,
            last_issue_obj: Any,
            current_issue_data: Dict
    ) -> Dict[str, Union[dict, bool, str]]:
        """
        <CODE PROCESSING> 状态，处理代码升级动作
        """
        # 更新 JiraIssue 表数据
        last_issue_obj.init_flag["code_init_flag"] += 1
        last_issue_obj.issue_status = "CODE PROCESSING"
        last_issue_obj.save()

        # 获取工单数据信息
        last_code_info = last_issue_obj.code_info
        current_issue_key = current_issue_data["issue_key"]
        current_code_info = current_issue_data["code_info"]
        current_summary = current_issue_data["summary"]
        current_product_id = current_issue_data["product_id"]
        current_environment = current_issue_data["environment"]

        try:
            # code_info 数据为空，直接触发到下一流程
            if not bool(current_code_info):
                last_issue_obj.issue_status = "UPGRADED DONE"
                last_issue_obj.code_info = current_code_info
                last_issue_obj.save()
                jira_obj.change_transition(current_issue_key, "NoCodeUpgrade")
                self.webhook_return_data["msg"] = f"无代码需要升级，升级工单 {current_summary} 转换到状态 <UPGRADED DONE>"
                return self.webhook_return_data

            # TODO: 判断是否首次升级？

            # code_info 数据不为空，调用 thread_code_handle 函数执行多线程升级代码
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 开始升级代码，开始时间：{start_time}")
            code_res = thread_code_handle(
                last_code_info=last_code_info,
                current_code_info=current_code_info,
                product_id=current_product_id,
                environment=current_environment,
                issue_key=current_issue_key
            )
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 代码升级结束，结束时间：{end_time}")

            #  代码升级成功，执行流程转换状态到下一步
            if code_res["status"]:
                jira_obj.change_transition(current_issue_key, "CodeUpgradeSuccessful")
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} 代码升级成功，转换到状态 <UPGRADE DONE>"
                # TODO: 升级成功邮件通知
                # d_logger.info(completed_workflow_notice(start_time, end_time, current_summary, upgrade_info_list))
            # 代码升级失败，流程跳转 FIX PENDING
            else:
                jira_obj.change_transition(current_issue_key, "CodeUpgradeFailed")
                self.webhook_return_data["status"] = False
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} 代码升级失败，返回结果：{code_res}"
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = f"升级工单 {current_summary} <CODE PROCESSING> webhook 触发失败，异常原因：{traceback.format_exc()}"
            jira_obj.change_transition(current_issue_key, "CodeUpgradeFailed")
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_fix_pending(
            self,
            last_issue_obj: Any
    ):
        last_issue_obj.issue_status = "FIX PENDING"
        last_issue_obj.save()
        summary = last_issue_obj.summary

        try:
            self.webhook_return_data["msg"] = f"工单 {summary} <FIX PENDING> 状态 webhook 触发成功，等待人工修复数据"
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = f"工单 {summary} <FIX PENDING> 状态 webhook 触发失败，异常原因：{err.__str__()}"
        # self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

from typing import Dict, List, Union, Any, Tuple
from datetime import datetime
import traceback
from django.db.models import Q

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
            # 判断是否有 SQL 升级数据：触发进入下一步流程
            if not current_sql_info:
                self.webhook_return_data["msg"] = f"Jira工单被创建，工单名：{current_summary}，工单无SQL升级数据，触发转换 <NoSqlUpgrade> 到状态 <CONFIG PROCESSING>"
                jira_obj.change_transition(current_issue_key, "NoSqlUpgrade")
            else:
                self.webhook_return_data["msg"] = f"Jira工单被创建，工单名：{current_summary}，工单有SQL升级数据，触发转换 <TriggerSubmitSql> 到状态 <SQL PENDING>，执行提交 SQL 到 Archery 动作"
                jira_obj.change_transition(current_issue_key, "TriggerSubmitSql")
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = err.__str__()
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_sql_pending(
            self,
            last_issue_obj: Any,
            current_issue_data: Dict,
            sqlworkflow_ser: Any,
            sql_workflow_ins: Any
    ) -> Dict:
        # 更新 JiraIssue 表数据
        last_issue_obj.init_flag["sql_init_flag"] += 1
        last_issue_obj.status = "SQL PENDING"
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
            sql_submit_res = sql_submit_handle(
                sql_info=current_sql_info,
                environment=current_environment
            )  # TODO

            # sql 提交成功，执行流程转换状态到下一步
            if sql_submit_res["status"]:
                jira_obj.change_transition(current_issue_key, "SubmitSqlSuccessful")
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} 触发转换 <SubmitSqlSuccessful> 到状态 <SQL PROCESSING>"
            # sql 提交失败，流程跳转 FIX PENDING
            else:
                jira_obj.change_transition(current_issue_key, "SubmitSqlFailed")
                self.webhook_return_data["status"] = False
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} 触发转换 <SubmitSqlFailed> 到状态 <FIX PENDING>"
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = f"<SQL PENDING> 状态 webhook 触发失败，异常原因：{traceback.format_exc()}"
            jira_obj.change_transition(current_issue_key, "SubmitSqlFailed")
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_sql_processing(
            self,
            last_issue_obj: Any,
            sql_workflow_ins: Any,
            current_issue_data: Dict
    ) -> Dict:
        # 更新 JiraIssue 表数据
        last_issue_obj.init_flag["sql_init_flag"] += 1
        last_issue_obj.status = "SQL PROCESSING"
        last_issue_obj.save()

        # 获取工单数据信息
        current_issue_key = current_issue_data["issue_key"]
        current_sql_info = current_issue_data["sql_info"]
        current_summary = current_issue_data["summary"]
        current_environment = current_issue_data["environment"]

        try:
            # 调用 sql_upgrade_handle 函数执行配置自动变更
            sql_upgrade_res = sql_upgrade_handle(
                sql_info=current_sql_info,
                environment=current_environment
            ) # TODO

            # sql 升级成功，执行流程转换状态到下一步
            if sql_upgrade_res["status"]:
                jira_obj.change_transition(current_issue_key, "SqlUpgradeSuccessful")
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} 触发转换 <SqlUpgradeSuccessful> 到状态 <CONFIG PROCESSING>"
            # sql 升级失败，流程跳转 FIX PENDING
            else:
                jira_obj.change_transition(current_issue_key, "SqlUpgradeFailed")
                self.webhook_return_data["status"] = False
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} 触发转换 <SqlUpgradeFailed> 到状态 <FIX PENDING>"
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = f"<SQL PENDING> 状态 webhook 触发失败，异常原因：{traceback.format_exc()}"
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
        last_issue_obj.status = "CONFIG PROCESSING"
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
                self.webhook_return_data["msg"] = f"无配置升级，升级工单 {current_summary} 触发转换 <NoConfigUpgrade> 到状态 <CODE PROCESSING>"

            # nacos_info 数据不为空，调用 nacos_handle 函数执行配置自动变更
            nacos_res = nacos_handle(
                nacos_info=current_nacos_info,
                product_id=current_product_id,
                environment=current_environment
            )

            # nacos 变更执行成功，执行流程转换状态到下一步
            if nacos_res["status"]:
                jira_obj.change_transition(current_issue_key, "ConfigUpgradeSuccessful")
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} Nacos 配置变更执行成功"
            # 变更执行失败，流程跳转 FIX PENDING
            else:
                jira_obj.change_transition(current_issue_key, "ConfigUpgradeFailed")
                self.webhook_return_data["status"] = False
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} Nacos 配置变更执行失败，返回：{nacos_res}"
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = f"<CONFIG PROCESSING> 状态 webhook 触发失败，异常原因：{traceback.format_exc()}"
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
        last_issue_obj.status = "CODE PROCESSING"
        last_issue_obj.save()

        # 获取工单数据信息
        current_issue_key = current_issue_data["issue_key"]
        current_code_info = current_issue_data["code_info"]
        current_summary = current_issue_data["summary"]
        current_environment = current_issue_data["environment"]

        try:
            # code_info 数据为空，直接触发到下一流程
            if not bool(current_code_info):
                last_issue_obj.status = "UPGRADED DONE"
                last_issue_obj.code_info = current_code_info
                last_issue_obj.save()
                jira_obj.change_transition(current_issue_key, "NoCodeUpgrade")
                self.webhook_return_data["msg"] = f"无代码需要升级，升级工单 {current_summary} 触发转换 <NoCodeUpgrade> 到状态 <UPGRADED DONE>"
                return self.webhook_return_data

            # TODO: 多次迭代升级代码时，只升级差异部分

            # 待升级的 code_info 列表数据，需转化为列表数据格式
            current_code_info_list = format_code_info(current_code_info, current_environment)
            wait_upgrade_list = current_code_info_list
            # 成功升级的列表数据
            upgrade_success_list = []
            # 升级成功的工程名称列表，用于邮件发送结果
            upgrade_info_list = []

            # 升级代码主逻辑
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 开始升级代码，开始时间：{start_time}")
            upgrade_success_list, upgrade_info_list = thread_code_handle(
                wait_upgrade_list,
                upgrade_success_list,
                upgrade_info_list
            )
            end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            d_logger.info(f"工单 {current_summary} 代码升级结束，结束时间：{end_time}")

            # 只有全部升级成功才转换为 CodeUpgradeSuccessful，只要有失败的升级就转换为 CodeUpgradeFailed
            if upgrade_success_list == current_code_info_list or not compare_list_info(upgrade_success_list, current_code_info_list):
                last_issue_obj.status = "UPGRADED DONE"
                last_issue_obj.code_info = current_code_info
                last_issue_obj.save()
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} 代码升级成功"
                self.webhook_return_data['data'] = {"已升级信息列表": upgrade_info_list}
                jira_obj.change_transition(current_issue_key, "CodeUpgradeSuccessful")
                # 发送升级成功邮件通知
                d_logger.info(completed_workflow_notice(start_time, end_time, current_summary, upgrade_info_list))
            else:
                self.webhook_return_data["status"] = False
                self.webhook_return_data["msg"] = f"升级工单 {current_summary} 代码升级失败，检查日志"
                jira_obj.change_transition(current_issue_key, "CodeUpgradeFailed")
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = f"<CODE PROCESSING> 状态 webhook 触发失败，异常原因：{traceback.format_exc()}"
            jira_obj.change_transition(current_issue_key, "CodeUpgradeFailed")
        self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

    def updated_event_fix_pending(
            self,
            last_issue_obj: Any
    ):
        last_issue_obj.status = "FIX PENDING"
        last_issue_obj.save()
        summary = last_issue_obj.summary

        try:
            self.webhook_return_data["msg"] = f"工单 {summary} <FIX PENDING> 状态 webhook 触发成功，等待人工修复数据"
        except Exception as err:
            self.webhook_return_data["status"] = False
            self.webhook_return_data["msg"] = f"工单 {summary} <FIX PENDING> 状态 webhook 触发失败，异常原因：{err.__str__()}"
        # self.webhook_return_data['data'] = current_issue_data
        return self.webhook_return_data

import requests
from typing import Dict, Union, Literal
from datetime import datetime,timedelta
from ast import literal_eval
from utils.getconfig import GetYamlConfig

__all__ = ["ArcheryAPI"]

class ArcheryAPI(object):
    def __init__(
            self,
            host: str = "",
            username: str = "",
            password: str = "",
            executable_time_range: int = 3
    ):
        self._username = username
        self._password = password
        self.token_url = host + "/auth/token/"
        self.refresh_url = host + "/auth/token/refresh/"
        self.verify_url = host + "/auth/token/verify/"
        self.resource_group_url = host + "/v1/user/resourcegroup/"
        self.instance_url = host + "/v1/instance/"
        self.workflow_url = host + "/v1/workflow/"
        self.audit_workflow_url = host + "/v1/workflow/audit/"
        self.execute_workflow_url = host + "/v1/workflow/execute/"
        self.executable_time_range = executable_time_range
        self._api_headers = {
            "content-type": "application/json",
            "authorization": ""
        }

    @staticmethod
    def _login_required(func):
        def wrapper(self, *args, **kwargs):
            try:
                # 获取 Archery 配置
                archery_config = GetYamlConfig().get_config("Archery")
                username = self._username if self._username else archery_config.get("username")
                password = self._password if self._password else archery_config.get("password")

                login_headers = {
                    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                }
                token_req_data = {
                    "username": username,
                    "password": password,
                }
                # init login
                token_res_data = requests.post(url=self.token_url, data=token_req_data, headers=login_headers).json()
                refresh_req_data = {
                    "refresh": token_res_data["refresh"]
                }
                # get refresh token
                refresh_res_data = requests.post(url=self.refresh_url, data=refresh_req_data, headers=login_headers).json()
                _api_token = "Bearer " + refresh_res_data["access"]
                self._api_headers["authorization"] = _api_token
                result = func(self, *args, **kwargs)
                return result
            except Exception as err:
                return_data = {
                    "status": False,
                    "msg": f"登录 Archery 失败，异常原因：{err.__str__()}"
                }
                return return_data
        return wrapper

    @_login_required
    def get_workflow(
            self,
            w_id: int = 0,
            size: int = 100,
    ) -> Dict[str, Union[bool, str, Dict]]:
        return_data = {
            "status": False,
            "msg": "",
            "data": dict()
        }
        data = {
            "id": w_id,
            "size": size
        }
        try:
            res = requests.get(url=self.workflow_url, params=data, headers=self._api_headers)
            if res.status_code == 200:
                res_json = res.json()
                assert res_json["count"], "查询工单结果为空"
                archery_results = res_json["results"][0]["workflow"]

                return_data["status"] = True
                return_data["msg"] = "查询工单成功"
                return_data["data"] = {
                    "w_id": archery_results["id"],
                    "w_status": archery_results["status"],
                    "instance": archery_results["instance"],
                    "group_id": archery_results["group_id"],
                    "db_name": archery_results["db_name"],
                    "workflow_name": archery_results["workflow_name"]
                }
            else:
                return_data["msg"] = f"查询工单失败，Archery 接口返回 {res.text}"
        except AssertionError as err:
            return_data["msg"] = err.__str__()
        except Exception as err:
            return_data["msg"] = f"查询工单异常，异常原因: {err.__str__()}"
        return return_data

    @_login_required
    def get_resource_group(
            self,
            resource_name: str = None
    ):
        return_data = {
            "status": False,
            "msg": "",
            "data": dict()
        }
        try:
            res = requests.get(url=self.resource_group_url, headers=self._api_headers)
            if res.status_code == 200:
                res_json = res.json()

                assert res_json["count"], "查询实例信息结果为空"
                archery_results = res_json["results"]
                for archery_result in archery_results:
                    if archery_result["group_name"] == resource_name:
                        return_data["data"] = archery_result
                assert return_data["data"], f"查询资源组 {resource_name} 不存在 Archery 资源组列表中"

                return_data["status"] = True
                return_data["msg"] = "查询资源组信息成功"
            else:
                return_data["msg"] = f"查询资源组信息失败，Archery 接口返回 {res.text}"
        except AssertionError as err:
            return_data["msg"] = err.__str__()
        except Exception as err:
            return_data["msg"] = f"查询资源组信息异常，异常原因：{err}"
        return return_data

    @_login_required
    def get_instance(
            self,
            instance_name: str = None,
            size: int = 100
    ):
        return_data = {
            "status": False,
            "msg": "",
            "data": dict()
        }
        try:
            data = {
                "size": size
            }
            res = requests.get(url=self.instance_url, params=data, headers=self._api_headers)
            if res.status_code == 200:
                res_json = res.json()
                assert res_json["count"], "查询实例信息结果为空"
                archery_results = res_json["results"]

                for archery_result in archery_results:
                    if archery_result["instance_name"] == instance_name:
                        return_data["data"] = archery_result
                assert return_data["data"], f"查询实例 {instance_name} 不存在 Archery 实例列表中"

                return_data["status"] = True
                return_data["msg"] = "查询实例信息成功"
            else:
                return_data["msg"] = f"查询实例信息失败, Archery 接口返回 {res.text}"
        except AssertionError as err:
            return_data["msg"] = err.__str__()
        except Exception as err:
            return_data["msg"] = f"查询实例信息异常，异常原因：{err}"
        return return_data

    @_login_required
    def commit_workflow(
            self,
            sql_index: int = 0,
            sql_filename: str = None,
            sql_release_info: str = None,
            sql_content: str = None,
            workflow_name: str = None,
            demand_url: str = "问题描述",
            resource_name: str = None,
            instance_name: str = None,
            db_name: str = None,
            is_backup: bool = True,
            engineer: str = "cdflow"
    ) -> Dict[str, Union[str, Dict, bool]]:
        """
        Args:
            sql_index: SQL 执行序号
            sql_filename: SQL 文件名
            sql_release_info: SQL 版本信息
            sql_content: SQL 文件内容
            workflow_name: 工单名称
            demand_url: 问题描述链接
            resource_name: 资源组名称
            instance_name: 实例名称
            db_name: 数据库名称
            is_backup: 是否备份
            engineer: 发起人
        Returns:
            Dict: return_data
        """
        return_data = {
            "status": False,
            "msg": "",
            "data": dict()
        }
        try:
            assert sql_content, "提交工单失败，sql 文件内容不能为空或 None"

            # 调用 get_resource_group 方法，通过 resouce_group_name 获取 group_id
            resource_group_info = self.get_resource_group(resource_name=resource_name)
            assert resource_group_info["status"], "查询资源组失败，检查 resource_name 参数"
            group_id = resource_group_info["data"]["group_id"]

            # 调用 get_instance 方法，通过 instance_name 获取 instance_id 和 db_name
            instance_info = self.get_instance(instance_name=instance_name)
            assert instance_info["status"], "查询实例信息失败，检查 instance_name 参数"
            instance_id = instance_info["data"]["id"]
            db_name = db_name if db_name else instance_info["data"]["db_name"]

            # 调用 Archery openapi workflow 接口提交工单
            current_time = datetime.now()
            future_time = current_time + timedelta(days=self.executable_time_range)
            data = {
                "sql_content": sql_content,  # sql content
                "workflow": {
                    "sql_index": sql_index,
                    "sql_release_info": sql_release_info,
                    "workflow_name": workflow_name,
                    "demand_url": demand_url,
                    "group_id": group_id,
                    "instance": instance_id,
                    "db_name": db_name,
                    "is_backup": is_backup,
                    "engineer": engineer,
                    "run_date_start": str(current_time),
                    "run_date_end": str(future_time)
                },
            }
            res = requests.post(url=self.workflow_url, json=data, headers=self._api_headers)
            if res.status_code == 201:
                # workflow_abort                工作流中止
                # workflow_autoreviewwrong      工作流程自动审核错误
                # workflow_exception            工作流异常
                # workflow_executing            工作流执行
                # workflow_finish               工作流程完成
                # workflow_manreviewing         工作流程人员审查
                # workflow_queuing              工作流排队
                # workflow_review_pass          工作流程review_pass
                # workflow_timingtask           工作流计时任务
                # workflow_manreviewing         提交成功等待审核
                res_json = res.json()
                w_id = res_json["workflow"]["id"]
                w_status = res_json["workflow"]["status"]

                return_data["status"] = True
                return_data["msg"] = f"工单 {workflow_name} 提交成功，等待审核"
                return_data["data"] = {
                    "w_id": w_id,
                    "sql_index": sql_index,
                    "sql_release_info": sql_release_info,
                    "workflow_name": workflow_name,
                    "w_status": w_status,
                    "sql_filename": sql_filename
                }
            else:
                return_data["msg"] = f"工单 {workflow_name} 提交失败，检查 Archery 日志"
                return_data["data"] = res.text
        except AssertionError as err:
            return_data["msg"] = err.__str__()
        except Exception as err:
            return_data["msg"] = f"提交工单异常，异常原因: {err.__str__()}"
        return return_data

    @_login_required
    def audit_workflow(
            self,
            engineer: str = "cdflow",
            workflow_id: int = None,
            audit_remark: str = "API 自动审核通过",
            # 工单类型：1-查询权限申请，2-SQL上线申请，3-数据归档申请
            workflow_type: Literal[1, 2, 3] = 2,
            # 审核类型：pass-通过，cancel-取消
            audit_type: Literal["pass", "cancel"] = "pass",
    ) -> Dict:
        """
        调用 Archery 接口将后台工单审核通过，进入待执行状态
        """
        return_data : Dict[str, Union[str, Dict, bool]] = {
            "status": False,
            "msg": "",
            "data": {}
        }
        if workflow_id is None:
            return_data["msg"] = "自动审核通过失败，工作流 ID 不能为空或 None"
            return return_data

        try:
            audit_data = {
                "engineer": engineer,
                "workflow_id": workflow_id,
                "audit_remark": audit_remark,
                "workflow_type": workflow_type,
                "audit_type": audit_type
            }
            res = requests.post(url=self.audit_workflow_url, json=audit_data, headers=self._api_headers)
            if res.status_code == 200:
                return_data["status"] = True
                return_data["msg"] = f"API 自动审核工单通过。"
            else:
                return_data["msg"] = f"API 自动审核工单失败，返回状态非200，请检查原因。"
            return_data["data"] = res.text
        except Exception as err:
            return_data["msg"] = f"API 自动审核工单异常，异常原因: {err.__str__()}"
        return return_data

    @_login_required
    def execute_workflow(
            self,
            engineer: str = "cdflow",
            workflow_id: int = None,
            # 工单类型：1-查询权限申请，2-SQL上线申请，3-数据归档申请
            workflow_type: Literal[1, 2, 3] = 2,
            # 执行模式：auto-线上执行，manual-已手动执行
            mode: Literal["auto", "manual"] = "auto",
    ) -> Dict:
        """
        调用 Archery 接口将后台工单自动线上执行（操作风险高，谨慎调用）
        """
        return_data : Dict[str, Union[str, Dict, bool]] = {
            "status": False,
            "msg": "",
            "data": {}
        }
        try:
            execute_data = {
                "engineer": engineer,
                "workflow_id": workflow_id,
                "workflow_type": workflow_type,
                "mode": mode
            }
            res = requests.post(url=self.execute_workflow_url, json=execute_data, headers=self._api_headers)
            if res.status_code == 200:
                return_data["status"] = True
                return_data["msg"] = f"工单自动执行成功。"
            else:
                return_data["msg"] = f"工单自动执行失败，返回状态非200，请检查原因。"
        except Exception as err:
            return_data["msg"] = f"工单自动执行异常，异常原因: {err.__str__()}"
        return return_data

if __name__ == "__main__":
    pass
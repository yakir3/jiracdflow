import requests
from typing import Dict, List, Union, Any, Tuple

__all__ = ["CmdbAPI"]

class CmdbAPI:
    def __init__(
            self,
            host: str = "",
            token: str = ""
    ):
        self.search_url = host + "/api/upgrade_release_vmc"
        self.upgrade_url = host + "/api/upgrade/upgrade/"
        self.upgrade_v2_url = host + "/api/upgrade/upgrade/v2/"
        self._api_headers = {
            "content-type": "application/json",
            "access-token": token,
        }

    # 通过 project_name 查询 id，返回工程 id 用于升级
    def search_by_project_name(
            self,
            service_name: str = None,
            environment: str = "UAT",
            vmc_host: str = None
    ) -> Dict[str, Union[bool, str, int]]:
        return_data = {
            "status": False,
            "msg": "",
            "pid": 0
        }
        try:
            # 通过 cmdb_vmc_host + service_name 调用 CMDB <升级发布> 接口获取对应 environment 的服务信息
            data = {
                "page": 1,
                "size": 50,
                "service_name": service_name,
                "vmc_host": vmc_host
            }
            cmdb_req = requests.get(url=self.search_url, json=data, headers=self._api_headers)
            # 根据返回状态返回结果
            if cmdb_req.status_code == 200:
                cmdb_req_json = cmdb_req.json()
                # fix: 返回多个 item 时，使用 service_name 过滤唯一值
                project_items = cmdb_req_json["data"]["items"]
                real_project_item = [p for p in project_items if p["project"]["service_name"] == service_name]
                pid = real_project_item[0]["id"]

                return_data["status"] = True
                return_data["msg"] = "查询<升级发布>工程 ID 成功"
                return_data["pid"] = pid
            else:
                return_data["msg"] = f"查询 CMDB <升级发布>接口返回非200状态, 返回数据 {cmdb_req.text}"
        except Exception as err:
            return_data["status"] = False
            return_data["msg"] = f"查询<升级发布>工程 ID 异常，异常原因：{err}"
        return return_data

    def project_deploy(
            self,
            service_name: str = None,
            code_version: str = None,
            branch: str = "uat1",
            environment: str = "UAT",
            vmc_host: str = ""
    ) -> Dict[str, Union[bool, str, Dict]]:
        """
        Args:
            service_name: my-app
            code_version: a1b2c3
            branch: master | uat1 | uat2 | uat3 ..
            environment: UAT | PROD
            vmc_host: 1.1.1.1
        Returns:
            {
                "status": True,
                "msg": "工程：my-app <升级发布> 成功",
                "data": {
                    "service_name": "my-app",
                    "code_version": None,
                    "branch": "uat1",
                    "environment": "UAT"
                }
            }
        """
        # 返回数据
        return_data = {
            "status": False,
            "msg": f"工程：{service_name} <升级发布> 失败",
            "data": {
                "service_name": service_name,
                "code_version": code_version,
                "branch": branch,
                "environment": environment
            }
        }
        try:
            # 通过 service_name + vmc_host 获取<升级发布>工程 ID
            search_project_result = self.search_by_project_name(service_name=service_name, environment=environment, vmc_host=vmc_host)
            assert search_project_result["status"], f"工程 {service_name} 获取 CMDB <升级发布> ID 失败，失败原因：{search_project_result['msg']}"

            # 调用 CMDB upgrade v2 接口升级代码
            pid = search_project_result["pid"]
            url = self.upgrade_v2_url + str(pid)
            upgrade_data = {
                "id": pid,
                "branch": branch,
                "version": code_version,
            }
            cmdb_req = requests.post(url=url, json=upgrade_data, headers=self._api_headers)
            # 获取升级结果返回
            if cmdb_req.status_code == 200:
                # cmdb_req_json = cmdb_req.json()
                return_data["status"] = True
                return_data["msg"] = f"工程：{service_name} <升级发布> 成功，版本：{code_version}，分支：{branch}"
            else:
                return_data["msg"] = f"执行 CMDB <升级发布>接口返回非200状态, 返回数据 {cmdb_req.text}"
            return return_data
        except Exception as err:
            return_data["status"] = False
            return_data["msg"] = f"调用 CMDB <升级发布> 异常，异常原因：{err}"
        return return_data

if __name__ == "__main__":
    pass
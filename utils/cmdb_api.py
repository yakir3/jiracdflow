import json
import requests
from ast import literal_eval
from utils.getconfig import GetYamlConfig
from typing import Dict, List, Union, Any, Tuple

__all__ = ["CmdbAPI"]

class CmdbAPI:
    def __init__(
            self,
            main_url: str = "https://cmdb.opsre.net",
            token: str = None
    ):
        self.search_url = main_url + "/api/upgrade_release_vmc"
        self.upgrade_url = main_url + "/api/upgrade/upgrade/"
        self.upgrade_v2_url = main_url + "/api/upgrade/upgrade/v2/"

    @staticmethod
    def _login_required(func):
        def wrapper(self, *args, **kwargs):
            try:
                # 获取 CMDB 配置信息
                cmdb_config = GetYamlConfig().get_config("CMDB")
                token = cmdb_config.get("token")
                self._api_headers = {
                    "content-type": "application/json",
                    "access-token": token,
                }
                result = func(self, *args, **kwargs)
                return result
            except Exception as err:
                return_data = {
                    "status": False,
                    "msg": f"CMDB 鉴权失败，异常原因：{err.__str__()}"
                }
                return return_data
        return wrapper

    # 通过 project_name 查询 id，返回工程 id 用于升级
    @_login_required
    def search_by_project_name(
            self,
            project_name: str = None,
            tag: str = None,
            environment: str = "UAT"
    ) -> Dict[str, Union[bool, str, int]]:
        return_data = {
            "status": False,
            "msg": "",
            "pid": 0
        }
        try:
            # 调整 project_name 字段为大写+下划线格式
            upper_project_name = project_name.upper().replace("-", "_")

            # 根据 env 调整 project_name 字段真实名称, UAT 或 PROD
            if environment == "PROD":
                real_project_name = upper_project_name
            else:
                real_project_name = f"{environment.upper()}_{upper_project_name}"

            # 请求 CMDB 接口，获取 ID
            data = {
                "page": 1,
                "size": 50,
                "name": real_project_name
            }
            cmdb_req = requests.get(url=self.search_url, json=data, headers=self._api_headers)
            if cmdb_req.status_code == 200:
                cmdb_req_json = cmdb_req.json()
                return_data["status"] = True
                return_data["msg"] = "查询<升级发布>工程 ID 成功"
                return_data["pid"] = cmdb_req_json["data"]["items"][0]["id"]
            else:
                return_data["msg"] = f"查询 CMDB <升级发布>接口返回非200状态, 返回数据 {cmdb_req.text}"
        except Exception as err:
            return_data["status"] = False
            return_data["msg"] = f"查询<升级发布>工程 ID 异常，异常原因：{err}"
        return return_data

    @_login_required
    def project_deploy(
            self,
            project_name: str = None,
            tag: str = "v1",
            code_version: str = None,
            environment: str = "UAT",
    ) -> Dict[str, Union[bool, str, List, Dict]]:
        """
        Args:
            project_name: my-app
            tag: v1 | v2 | v3 ..
            code_version: a1b2c3
            environment: UAT | PROD
        Returns:
            {
                "status": True,
                "msg": "工程：my-app <升级发布> 成功",
                "data": {
                    "notice_project_name": "UAT_MY_APP_V2",
                    "project_name": "my-app",
                    "code_version": None,
                    "tag": "v2"
                }
            }
        """
        # 返回数据，兼容 v1 v2 版本的升级接口
        return_data = {
            "status": False,
            "msg": f"工程：{project_name} <升级发布> 失败",
            "data": {
                "project_name": project_name,
                "code_version": code_version,
                "tag": tag,
                "environment": environment
            },
            "notice_flags": None
        }

        try:
            # 通过 project_name 获取<升级发布>工程 ID
            project_info = self.search_by_project_name(project_name=project_name, tag=tag, environment=environment)
            assert project_info["status"], f"工程 {project_name} 获取 CMDB <升级发布> ID 失败，失败原因：{project_info['msg']}"

            # 根据 env 判断升级环境
            if environment == "PROD":
                real_branch = "master"
            else:
                real_branch = f"release_uat_{tag[-1]}"

            # 调用 CMDB upgrade v2 接口升级代码
            pid = project_info["pid"]
            url = self.upgrade_v2_url + str(pid)
            upgrade_data = {
                "id": pid,
                "branch": real_branch,
                "version": code_version,
            }
            cmdb_req = requests.post(url=url, json=upgrade_data, headers=self._api_headers)
            # 获取升级结果返回
            if cmdb_req.status_code == 200:
                cmdb_req_json = cmdb_req.json()
                return_data["status"] = True
                return_data["msg"] = f"工程：{project_name} <升级发布> 成功，版本：{code_version}，环境：{tag}"
                # notice_flags = project_name
                notice_flags = cmdb_req_json["data"].get("project", f"{project_name}")
                return_data["notice_flags"] = notice_flags
            return return_data
        except Exception as err:
            return_data["status"] = False
            return_data["msg"] = f"调用 CMDB <升级发布> 异常，异常原因：{err.__str__()}"
        return return_data

if __name__ == "__main__":
    pass
#!/usr/bin/python
import requests
from typing import Union, Dict
try:
    from getconfig import GetYamlConfig
except:
    from util.getconfig import GetYamlConfig

# 获取配置
archery_config = GetYamlConfig().get_config('Archery')

__all__ = ['ArcheryAPI']

_url_list = {

}

class ArcheryAPI(object):
    """ Archery 实例，使用 requests 模块调用接口提交、查询 SQL 工单等

    Attributes:
    """
    # code 0 -> 成功
    # code 1 -> 失败
    return_data = {'code': 1, 'msg': ''}
    def __init__(self, headers=None):
        self.username = archery_config['auth']['username']
        self.password = archery_config['auth']['password']
        self.token_url = archery_config['auth']['token_url']
        self.refresh_url = archery_config['auth']['refresh_url']
        self.sql_ticket_url = archery_config['v1']['sql_ticket_url']
        self.headers = headers

    def _get_token(self) -> Dict:
        access_token_data = {'username': self.username, 'password': self.password}
        refresh_token_data = {'refresh': ''}
        try:
            access_token_result = requests.post(url=self.token_url, json=access_token_data)
            if access_token_result.status_code == 200:
                access_key = access_token_result.json()['access']
                # refresh_key = access_token_result.json()['refresh']
                # refresh_token_data['refresh'] = refresh_key
                # refresh_token_result = requests.post(url=self.refresh_url, json=refresh_token_data)
                self.return_data['code'] = 0
                self.return_data['msg'] = f"获取 Archery Token 成功"
                self.return_data['token'] = access_key
            else:
                self.return_data['msg'] = f"获取 Archery Token 失败，响应内容：{access_token_result.text}"
            return self.return_data
        except Exception as err:
            self.return_data['msg'] = f"请求 Archery Token 接口异常，错误信息：{err}"
            return self.return_data

    def submit_sql_ticket(
            self,
            workflow_name: str, # 邮件标题
            demand_url: str,    # 工单链接
            group_id: int,      # 资源组 ID
            instance_id: int,      # 数据库实例 ID
            db_name: str,       # 数据库名称
            run_date_start: str,  # 工单可执行开始时间
            run_date_end: str,    # 工单可执行结束时间
            is_backup: bool = True,
            engineer: str = "cdflow",
            sql_content: str = None
    ) -> Dict:
        """ 提交 SQL 工单
        Args:
            ...
        Returns:
            Dict: return_data
        """
        try:
            token = "Bearer " + self._get_token().pop('token')
            self.headers = {'Authorization': token}
            data = {
                "workflow": {
                    "workflow_name": workflow_name,
                    "demand_url": demand_url,
                    "group_id": group_id,
                    "instance": instance_id,
                    "db_name": db_name,
                    "run_date_start": run_date_start,
                    "run_date_end": run_date_end,
                    "is_backup": is_backup,
                    "engineer": engineer,
                },
                "sql_content": sql_content
            }
            submit_sql_result = requests.post(url=self.sql_ticket_url, json=data, headers=self.headers)
            assert submit_sql_result.ok, "提交 SQL 工单响应结果非200."
            self.return_data['code'] = 0
            self.return_data['workflow_name'] = workflow_name
            self.return_data['msg'] = f"提交 SQL 工单到 Archery 成功."
            self.return_data['data'] = submit_sql_result.json()
            return self.return_data
        except Exception as err:
            self.return_data['code'] = 1
            self.return_data['workflow_name'] = workflow_name
            self.return_data['msg'] = f"提交 SQL 工单到 Archery 异常，错误信息：{err}"
            return self.return_data

    def get_instance_info(
            self
    ) -> Dict:
        """ 获取实例清单
        Args:
            ...
        Returns:
            Dict: return_data
        """
        try:
            token = "Bearer " + self._get_token().pop('token')
            self.headers = {'Authorization': token}
            data = {
                'size': 100,  # 查询实例数量
            }
            instance_url = 'https://uat-archery-api.opsre.net/api/v1/instance/'
            request_result = requests.get(url=instance_url, params=data, headers=self.headers)
            assert request_result.ok, "提交 SQL 工单响应结果非200."

            return request_result.json()
        except Exception as err:
            print(err.__str__())
            return 'False'

if __name__ == '__main__':
    print(archery_config['schema'])
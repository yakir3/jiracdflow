import requests
from typing import Dict, Union, Literal
from datetime import datetime,timedelta
from ast import literal_eval
from utils.getconfig import GetYamlConfig

__all__ = ['ArcheryAPI']

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
                archery_config = GetYamlConfig().get_config('Archery')
                username = self._username if self._username else archery_config.get('username')
                password = self._password if self._password else archery_config.get('password')

                login_headers = {
                    'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                }
                token_req_data = {
                    'username': username,
                    'password': password,
                }
                # init login
                token_res_data = requests.post(url=self.token_url, data=token_req_data, headers=login_headers).json()
                refresh_req_data = {
                    'refresh': token_res_data['refresh']
                }
                # get refresh token
                refresh_res_data = requests.post(url=self.refresh_url, data=refresh_req_data, headers=login_headers).json()
                _api_token = 'Bearer ' + refresh_res_data['access']
                self._api_headers['authorization'] = _api_token
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
    def get_workflows(
            self,
            w_id: int = 0,
            w_status: str = None,
            workflow_name: str = None,
            size: int = 100,
    ) -> Dict[str, Union[bool, str, Dict]]:
        return_data = {
            'status': False,
            'msg': '',
            'data': {}
        }
        data = {
            'id': w_id,
            'workflow__status': w_status,
            'workflow__workflow_name__icontains': workflow_name,
            'size': size
        }
        try:
            res = requests.get(url=self.workflow_url, params=data, headers=self._api_headers)
            if res.status_code == 200:
                res_data = res.json()
                if res_data['count'] == 0:
                    return_data['msg'] = '查询工单结果为空'
                    return_data['data'] = res_data
                else:
                    tmp_list = []
                    for index in range(res_data['count']):
                        name = res_data['results'][index]['workflow']['workflow_name']
                        wid = res_data['results'][index]['workflow']['id']
                        status = res_data['results'][index]['workflow']['status']
                        try:
                            execute_result = literal_eval(res_data['results'][index]['execute_result'])
                        except SyntaxError:
                            execute_result = ""
                        tmp_list.append({'name': name, 'id': wid, 'status': status, 'execute_result': execute_result})
                    return_data['status'] = True
                    return_data['msg'] = '查询工单成功。'
                    return_data['data'] = tmp_list
            else:
                return_data['msg'] = '查询工单失败，请求接口返回非200'
                return_data['data'] = res.text
        except Exception as err:
            return_data['msg'] = f"提交工单异常，异常原因: {err.__str__()}"
        return return_data

    @_login_required
    def get_resource_groups(
            self,
    ):
        return_data = {
            'status': False,
            'msg': '',
            'data': {}
        }
        try:
            res = requests.get(url=self.resource_group_url, headers=self._api_headers)
            res_data = res.json()
            if res.status_code == 200:
                result = {
                    res_data['results'][index]['group_name']:res_data['results'][index]['group_id'] for index in range(res_data['count'])
                }
                return_data['status'] = True
                return_data['msg'] = '查询资源组信息成功。'
                return_data['data'] = result
            else:
                return_data['msg'] = '查询资源组信息失败，请求接口返回非200'
                return_data['data'] = res_data
            return return_data
        except Exception as err:
            return_data['msg'] = f"查询资源组信息异常，异常原因：{err}"
            return return_data

    @_login_required
    def get_instances(
            self,
            instance_name: str = None,
    ):
        return_data = {
            'status': False,
            'msg': '',
            'data': {}
        }
        try:
            data = {
                'size': 100,  # 查询实例数量
            }
            res = requests.get(url=self.instance_url, params=data, headers=self._api_headers)
            res_data = res.json()
            if res.status_code == 200:
                tmp_data = {}
                for index in range(res_data['count']):
                    _instance_name = res_data['results'][index]['instance_name']
                    instance_id = res_data['results'][index]['id']
                    db_name = res_data['results'][index]['db_name']
                    if instance_name == _instance_name:
                        tmp_data[instance_name] = {'id': instance_id, 'db_name': db_name}
                return_data['status'] = True
                return_data['msg'] = '查询实例信息成功'
                return_data['data'] = tmp_data
            else:
                return_data['msg'] = '查询实例信息失败, 请求查询接口响应非200'
                return_data['data'] = res_data
            return return_data
        except Exception as err:
            return_data['msg'] = f"查询实例信息异常，异常原因：{err}"
            return return_data

    @_login_required
    def commit_workflow(
            self,
            sql_index: int = 0,
            sql_release_info: int = 0,
            sql_content: str = None,
            workflow_name: str = None,
            demand_url: str = '问题描述',
            resource_tag: str = None,
            instance_tag: str = None,
            db_name: str = None,
            is_backup: bool = True,
            engineer: str = 'cdflow'
    ) -> Dict[str, Union[str, Dict, bool]]:
        """
        Args:
            sql_index: SQL 执行序号
            sql_release_info: SQL 版本信息
            sql_content: SQL 文件内容
            workflow_name: 工单名称
            demand_url: 问题描述链接
            resource_tag: 资源组 ID
            instance_tag: 实例 ID
            db_name: 数据库名称
            is_backup: 是否备份
            engineer: 发起人
        Returns:
            Dict: return_data
        """
        return_data = {
            'status': False,
            'msg': '',
            'data': {}
        }
        if not sql_content:
            return_data['msg'] = '提交工单失败，sql 文件内容不能为空或 None'
            return return_data
        try:
            # 查询 group_id
            groups_info = self.get_resource_groups()
            if resource_tag not in groups_info['data'].keys():
                return_data['msg'] = groups_info['msg']
                return_data['data'] = groups_info['data']
                return return_data
            else:
                group_id = groups_info['data'][resource_tag]
            # 查询 instance_id 和 db_name
            instance_info = self.get_instances(instance_name=instance_tag)
            if not instance_info['status']:
                return_data['msg'] = instance_info['msg']
                return_data['data'] = instance_info['data']
                return return_data
            else:
                # 单实例多数据库时判断是否传 db_name
                db_name = db_name if db_name else instance_info['data'][instance_tag]['db_name']
                instance_id = instance_info['data'][instance_tag]['id']

            # req data
            current_time = datetime.now()
            future_time = current_time + timedelta(days=self.executable_time_range)
            data = {
                'sql_content': sql_content,  # sql content
                'workflow': {
                    'sql_index': sql_index,
                    'sql_release_info': sql_release_info,
                    'workflow_name': workflow_name,
                    'demand_url': demand_url,
                    'group_id': group_id,
                    'instance': instance_id,
                    'db_name': db_name,
                    'is_backup': is_backup,
                    'engineer': engineer,
                    'run_date_start': str(current_time),
                    'run_date_end': str(future_time)
                },
            }
            res = requests.post(url=self.workflow_url, json=data, headers=self._api_headers)
            res_data = res.json()
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
                if res_data['workflow']['status'] == 'workflow_manreviewing':
                    result_data = {
                        'w_id': int(res_data['workflow']['id']),
                        'sql_index': int(res_data['workflow']['sql_index']),
                        'sql_release_info': int(res_data['workflow']['sql_release_info']),
                        'workflow_name': res_data['workflow']['workflow_name'],
                        'w_status': res_data['workflow']['status']
                    }
                    result = {'status': True, 'msg': '提交工单成功,等待审核', 'data': result_data}
                else:
                    result = {'status': False, 'msg': '提交工单成功，状态异常,请登陆archery后台查看', 'data': ''}
                return result
            else:
                return {'status': False, 'msg': '提交工单失败', 'data': res.json()}
        except Exception as err:
            return_data['msg'] = f"提交工单异常，异常原因: {err.__str__()}"
        return return_data

    @_login_required
    def audit_workflow(
            self,
            engineer: str = 'cdflow',
            workflow_id: int = None,
            audit_remark: str = 'API 自动审核通过',
            # 工单类型：1-查询权限申请，2-SQL上线申请，3-数据归档申请
            workflow_type: Literal[1, 2, 3] = 2,
            # 审核类型：pass-通过，cancel-取消
            audit_type: Literal['pass', 'cancel'] = 'pass',
    ) -> Dict:
        """
        调用 Archery 接口将后台工单审核通过，进入待执行状态
        """
        return_data : Dict[str, Union[str, Dict, bool]] = {
            'status': False,
            'msg': '',
            'data': {}
        }
        if workflow_id is None:
            return_data['msg'] = '自动审核通过失败，工作流 ID 不能为空或 None'
            return return_data

        try:
            audit_data = {
                'engineer': engineer,
                'workflow_id': workflow_id,
                'audit_remark': audit_remark,
                'workflow_type': workflow_type,
                'audit_type': audit_type
            }
            res = requests.post(url=self.audit_workflow_url, json=audit_data, headers=self._api_headers)
            if res.status_code == 200:
                return_data['status'] = True
                return_data['msg'] = f"API 自动审核工单通过。"
            else:
                return_data['msg'] = f"API 自动审核工单失败，返回状态非200，请检查原因。"
            return_data['data'] = res.text
        except Exception as err:
            return_data['msg'] = f"API 自动审核工单异常，异常原因: {err.__str__()}"
        return return_data

    @_login_required
    def execute_workflow(
            self,
            engineer: str = 'cdflow',
            workflow_id: int = None,
            # 工单类型：1-查询权限申请，2-SQL上线申请，3-数据归档申请
            workflow_type: Literal[1, 2, 3] = 2,
            # 执行模式：auto-线上执行，manual-已手动执行
            mode: Literal['auto', 'manual'] = 'auto',
    ) -> Dict:
        """
        调用 Archery 接口将后台工单自动线上执行（操作风险高，谨慎调用）
        """
        return_data : Dict[str, Union[str, Dict, bool]] = {
            'status': False,
            'msg': '',
            'data': {}
        }
        try:
            execute_data = {
                'engineer': engineer,
                'workflow_id': workflow_id,
                'workflow_type': workflow_type,
                'mode': mode
            }
            res = requests.post(url=self.execute_workflow_url, json=execute_data, headers=self._api_headers)
            if res.status_code == 200:
                return_data['status'] = True
                return_data['msg'] = f"工单自动执行成功。"
            else:
                return_data['msg'] = f"工单自动执行失败，返回状态非200，请检查原因。"
        except Exception as err:
            return_data['msg'] = f"工单自动执行异常，异常原因: {err.__str__()}"
        return return_data

if __name__ == '__main__':
    pass
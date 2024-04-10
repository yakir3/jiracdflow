import requests
from typing import Dict, Union, Literal
from datetime import datetime,timedelta
from ast import literal_eval
from utils.getconfig import GetYamlConfig

# 获取配置
archery_config = GetYamlConfig().get_config('Archery')['auth']

__all__ = ['ArcheryAPI']

class ArcheryAPI(object):
    def __init__(self,archery_conf=archery_config):
        self.url = archery_conf.get('url')
        self.token_url = archery_conf.get('token_url')
        self.refresh_url = archery_conf.get('refresh_url')
        self.verify_url = archery_conf.get('verify_url')
        self.resource_group_url = archery_conf.get('resource_group_url')
        self.instance_url = archery_conf.get('instance_url')
        self.get_workflow_url = archery_conf.get('get_workflow_url')
        self.sql_run_max_time = 3 # 单位day
        self._username = archery_conf.get('username')
        self._password = archery_conf.get('password')
        self.headers = {
            'content-type' : 'application/json',
        }
        self.login_headers = {
            'content-type' : 'application/x-www-form-urlencoded; charset=UTF-8',
        }
        # init token
        token_data = {
            'username': self._username,
            'password': self._password,
        }
        token_res_data = requests.post(url=self.token_url, data=token_data, headers=self.login_headers).json()
        refresh_data = {
            'refresh': token_res_data['refresh']
        }
        refresh_res_data = requests.post(url=self.refresh_url, data=refresh_data, headers=self.login_headers).json()
        token = 'Bearer ' + refresh_res_data['access']
        self.headers['authorization'] = token

    def get_workflows(
            self,
            w_id: int = 0,
            w_status: str = None,
            workflow_name: str = None,
            size: int = 100
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
            res = requests.get(url=self.get_workflow_url, params=data, headers=self.headers)
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
                    return_data['msg'] = '查询工单正常返回'
                    return_data['data'] = tmp_list
            else:
                return_data['msg'] = '查询工单失败，请求接口返回非200'
                return_data['data'] = res.text
        except Exception as err:
            return_data['msg'] = f"提交工单异常，异常原因: {err.__str__()}"
        return return_data

    def workflow_times(self):
        now = datetime.now()
        end_time = now + timedelta(days=self.sql_run_max_time)
        return {
            'run_date_start': str(now),
            'run_date_end': str(end_time),
        }

    def get_resource_groups(self):
        return_data = {
            'status': False,
            'msg': '',
            'data': {}
        }
        try:
            res = requests.get(url=self.resource_group_url, headers=self.headers)
            res_data = res.json()
            if res.status_code == 200:
                result = {
                    res_data['results'][index]['group_name']:res_data['results'][index]['group_id'] for index in range(res_data['count'])
                }
                return_data['status'] = True
                return_data['msg'] = 'success'
                return_data['data'] = result
            else:
                return_data['msg'] = '查询资源组信息失败，请求接口返回非200'
                return_data['data'] = res_data
            return return_data
        except Exception as err:
            return_data['msg'] = f"查询资源组信息异常，异常原因：{err}"
            return return_data

    def get_instances(self, instance_name=None):
        return_data = {
            'status': False,
            'msg': '',
            'data': {}
        }
        try:
            data = {
                'size': 100,  # 查询实例数量
            }
            res = requests.get(url=self.instance_url, params=data, headers=self.headers)
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
                return_data['msg'] = '查询实例信息完成'
                return_data['data'] = tmp_data
            else:
                return_data['msg'] = '查询实例信息失败, 请求查询接口响应非200'
                return_data['data'] = res_data
            return return_data
        except Exception as err:
            return_data['msg'] = f"查询实例信息异常，异常原因：{err}"
            return return_data

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
            is_backup: bool = False,
            engineer: str = 'admin'
    ) -> Dict[str, Union[str, Dict, bool]]:
        """
        Args:
            sql_index:
            sql_release_info:
            sql_content:
            workflow_name:
            demand_url:
            resource_tag:
            instance_tag:
            db_name:
            is_backup:
            engineer:
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
            dates = self.workflow_times()
            # 查询 group_id
            groups_info = self.get_resource_groups()
            if resource_tag not in groups_info['data'].keys():
                return_data['msg'] = groups_info['msg']
                return_data['data'] = groups_info['data']
                return return_data
            else:
                group_id = groups_info['data'][resource_tag]
            # 查询 instance_id / db_name
            instance_info = self.get_instances(instance_name=instance_tag)
            if not instance_info['status']:
                return_data['msg'] = instance_info['msg']
                return_data['data'] = instance_info['data']
                return return_data
            else:
                # 单实例多数据库时判断是否传 db_name
                if db_name:
                    db_name = db_name
                else:
                    db_name = instance_info['data'][instance_tag]['db_name']
                instance_id = instance_info['data'][instance_tag]['id']

            data = {
                'sql_content': sql_content,  # sql content
                'workflow': {
                    'sql_index': sql_index,  # 工单SQL执行序号
                    'sql_release_info': sql_release_info,  # 工单SQL版本信息
                    'workflow_name': workflow_name,  # 工单名
                    'demand_url': demand_url,  # 问题描述
                    'group_id': group_id,  # 资源组id
                    'instance': instance_id,  # 实例ID
                    'db_name': db_name,  # 数据库名
                    'is_backup': is_backup,  # 是否备份
                    'engineer': engineer,  # 发起人
                },
            }
            data['workflow'] = dict(data['workflow'], **dates)
            url = self.url + '/v1/workflow/'
            res = requests.post(url=url, json=data, headers=self.headers)
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
                        'workflow_name': res_data['workflow']['workflow_name'],
                        'w_status': res_data['workflow']['status'],
                        'sql_index': int(res_data['workflow']['sql_index']),
                        'sql_release_info': int(res_data['workflow']['sql_release_info'])
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

    def audit_workflow(
            self,
            engineer: str = 'cdflow',
            workflow_id: int = None,
            audit_remark: str = 'API 自动审核通过',
            # 工单类型：1-查询权限申请，2-SQL上线申请，3-数据归档申请
            workflow_type: Literal[1, 2, 3] = 2,
            # 审核类型：pass-通过，cancel-取消
            audit_type: Literal['pass', 'cancel'] = 'pass') -> Dict:
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
            url = self.url + '/v1/workflow/audit/'
            res = requests.post(url=url, json=audit_data, headers=self.headers)
            if res.status_code == 200:
                return_data['status'] = True
                return_data['msg'] = f"API 自动审核工单通过。"
            else:
                return_data['msg'] = f"API 自动审核工单失败，返回状态非200，请检查原因。"
            return_data['data'] = res.text
        except Exception as err:
            return_data['msg'] = f"API 自动审核工单异常，异常原因: {err.__str__()}"
        return return_data

    def execute_workflow(
            self,
            engineer: str = 'cdflow',
            workflow_id: int = None,
            # 工单类型：1-查询权限申请，2-SQL上线申请，3-数据归档申请
            workflow_type: Literal[1, 2, 3] = 2,
            # 执行模式：auto-线上执行，manual-已手动执行
            mode: Literal['auto', 'manual'] = 'auto') -> Dict:
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
            url = self.url + '/v1/workflow/execute/'
            res = requests.post(url=url, json=execute_data, headers=self.headers)
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
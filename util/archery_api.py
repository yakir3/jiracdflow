import requests
from typing import Dict, Union, Literal
from datetime import datetime,timedelta
from ast import literal_eval
try:
    from getconfig import GetYamlConfig
except:
    from util.getconfig import GetYamlConfig

# 获取配置
archery_config = GetYamlConfig().get_config('Archery')['auth']

__all__ = ['ArcheryAPI']

class ArcheryAPI(object):
    def __init__(self,archery_conf=archery_config):
        self.url = archery_conf.get('url','https://uat-archery-api.opsre.net/api')
        self.sql_run_max_time = 3 #单位day
        self.__username = archery_conf.get('username')
        self.__password = archery_conf.get('password')
        self.headers = {
            'content-type' : 'application/json',
        }
        self.login_headers = {
            'content-type' : 'application/x-www-form-urlencoded; charset=UTF-8',
        }
        try:
            data = {
                'username': self.__username,
                'password': self.__password,
            }
            token_url = self.url + '/auth/token/'
            token_res_data = requests.post(url=token_url, data=data, headers=self.login_headers).json()
            refresh_url = self.url + '/auth/token/refresh/'
            data = {'refresh': token_res_data['refresh']}
            refresh_res_data = requests.post(url=refresh_url, data=data, headers=self.login_headers).json()
            token = 'Bearer ' + refresh_res_data['access']
            self.headers['authorization'] = token
        except Exception as e:
            print(f"archery init err: {e}")

    def get_workflows(self,args=dict):
        data = {
            'id': args.get('id'),
            'workflow__status':args.get('status'),
            'size':100,
            'workflow__workflow_name__icontains': args.get('workflow_name'),
        }
        try:
            url = self.url + '/v1/workflow/'
            res = requests.get(url=url,params=data,headers=self.headers)
            status = False
            msg = '查询完成'
            result = []
            if res.status_code == 200:
                res_data = res.json()
                if res_data['count'] == 0:
                     msg = '未查询到此work_flow信息'
                     result = res_data
                else:
                    for index in range(res_data['count']):
                        name = res_data['results'][index]['workflow']['workflow_name']
                        wid = res_data['results'][index]['workflow']['id']
                        status = res_data['results'][index]['workflow']['status']
                        try:
                            execute_result = literal_eval(res_data['results'][index]['execute_result'])
                        except SyntaxError:
                            execute_result = ""
                        result.append({'name': name, 'id': wid, 'status': status, 'execute_result': execute_result})
                        status = True
            else:
                msg = '查询失败'
                result = res.text
            return {'status':status,'msg':msg,'data':result}
        except Exception as e:
            return {'status':False,'msg':'查询异常','data':e}

    def get_full_workflows(
            self,
            workflow_name_icontains: str,
            # workflow_status: str = None,
            # workflow_id: int = 0,
            page: int = 1,
            size: int = 30,
    ):
        data = {
            'workflow__workflow_name__icontains': workflow_name_icontains,
            # 'workflow__status': workflow_status,
            # 'workflow_id': workflow_id,
            'page': page,
            'size': size,
        }
        try:
            url = self.url + '/v1/workflow/'
            res = requests.get(url=url,params=data,headers=self.headers)

        except Exception as err:
            return {
                'status': False,
                'msg': '工单查询异常',
                'data': err.__str__()
            }

    def workflow_times(self):
        now = datetime.now()
        end_time = now  + timedelta(days=self.sql_run_max_time)
        return {
            'run_date_start': str(now),
            'run_date_end': str(end_time),
        }

    def get_resource_groups(self):
        try:
            url = self.url + '/v1/user/resourcegroup/'
            res = requests.get(url=url,headers=self.headers)
            res_data = res.json()
            if res.status_code == 200:
                result = {
                    res_data['results'][index]['group_name']:res_data['results'][index]['group_id'] for index in range(res_data['count'])
                }
                status = True
            else:
                status = False
                result = res_data
            return {'status': status, 'msg': '查询资源组信息完毕', 'data': result}
        except Exception as e:
            return {'status': False, 'msg':'查询资源组信息异常','data':e}

    def get_instances(self, instance_name=None):
        try:
            url = self.url + '/v1/instance/'
            data = {
                'size': 100,  # 查询实例数量
            }
            res = requests.get(url=url, params=data, headers=self.headers)
            res_data = res.json()
            result = {}
            status = False
            if res.status_code == 200:
                for index in range(res_data['count']):
                    _instance_name = res_data['results'][index]['instance_name']
                    instance_id = res_data['results'][index]['id']
                    db_name = res_data['results'][index]['db_name']
                    if instance_name == _instance_name:
                        result[instance_name] = {'id': instance_id, 'db_name': db_name}
                        status = True
                msg = '查询实例不存在' if not status else '查询实例信息完毕'
            else:
                result = res_data
                msg = '查询实例失败'
            return {'status': status, 'msg': msg, 'data': result}
        except Exception as e:
            return {'status': False, 'msg': '查询实例信信息异常', 'data': e}

    def commit_workflow(self,args: Dict=dict):
        if not args['sql']:
            return {'status':False,'msg':'args[sql] is None','data':''}
        try:
            dates = self.workflow_times()
            #查询group_id
            groups_info = self.get_resource_groups()
            if args['resource_tag'] not in groups_info['data'].keys():
                return {'status':False,'msg':groups_info['msg'],'data':groups_info['data']}
            else:
                group_id = groups_info['data'][args['resource_tag']]
            #查询 instance_id / db_name
            instance_info = self.get_instances(instance_name=args['instance_tag'])
            if instance_info['status']:
                db_name = instance_info['data'][args['instance_tag']]['db_name']
                instance_id = instance_info['data'][args['instance_tag']]['id']
            else:
                return {'status':False,'msg':instance_info['msg'],'data':instance_info['data']}

            # 获取 sql_index 与 sql_release_info 数据
            sql_index = args.get('sql_index', 0)
            sql_release_info = args.get('sql_release_info', 0)
            # if not sql_index or not sql_release_info:
            #     return {'status': False, 'msg': 'sql_index 或 sql_release_info 值不能为空或 None，请重试', 'data': ''}

            data = {
                'sql_content': args['sql'], #sql *
                'workflow':{
                    'sql_index': sql_index,                             # 工单SQL执行序号
                    'sql_release_info': sql_release_info,               # 工单SQL版本信息
                    'workflow_name': args.get('workflow_name','工单名'), # 工单名
                    'demand_url': args.get('demand_url','描述链接'),     # 问题描述
                    'group_id': group_id,                               # 资源组id
                    'instance': instance_id,                            # 实例ID
                    'db_name': db_name,                                 # 数据库名
                    'is_backup': args.get('is_backup', False),          # 是否备份
                    'engineer': args.get('engineer','admin'),           # 发起人
                },
            }
            data['workflow'] = dict(data['workflow'],**dates)
            url = self.url + '/v1/workflow/'

            res = requests.post(url=url,json=data,headers=self.headers)
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
                    result = {'status': False, 'msg': '提交工单成功，状态异常,请登陆archery后台查看', 'data':''}
                return result
            else:
                return {'status':False,'msg':'提交工单失败','data':res.json()}
        except Exception as e:
            return {'status':False,'msg':'提交工单异常','data':e}

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
import json
import requests
from ast import literal_eval
try:
    from getconfig import GetYamlConfig
except:
    from util.getconfig import GetYamlConfig
from typing import Dict, List, Union, Any, Tuple

__all__ = ['CmdbAPI']

# 获取 JIRA 配置信息
cmdb_config = GetYamlConfig().get_config('CMDB')

class CmdbAPI:
    def __init__(self, config=cmdb_config):
        self.search_url = config.get('search_url')
        self.upgrade_url = config.get('upgrade_url')
        self.upgrade_v2_url = config.get('upgrade_v2_url')
        self.domain = config.get('domain')
        self.token = config.get('token')
        self.headers = {
            'content-type':'application/json',
            'access-token': self.token,
        }

    def search_info(self,
                    svn_path: str = None,
                    ) -> Dict:
        return_data = {
            'status': True,
            'msg': '',
            'data': dict()
        }
        try:
            svn_path = svn_path.lower()
            data = {
                "page": 1,
                "size": 50,
                "svn_path": svn_path,
            }
            if svn_path.startswith('/'): svn_path = svn_path[1:]
            cmdb_req = requests.get(url=self.search_url, data=json.dumps(data), headers=self.headers)
            assert cmdb_req.status_code == 200, 'cmdb interface returns status code is not 200!'

            # get information by cmdb
            cmdb_result = cmdb_req.json()
            project_name = [ x['project']['name'] for x in cmdb_result['data']['items']if 'UAT' not in x['project']['name'] ][0]
            project_version = [ x['arg'] for x in cmdb_result['data']['items'] if 'UAT' not in x['project']['name'] ][0]

            return_data['msg'] = 'cmdb search prod project info success.'
            return_data['data'] = {
                'project_name': project_name,
                'project_version': project_version
            }
        except Exception as err:
            return_data['status'] = False
            return_data['msg'] = err.__str__()
        return return_data

    def search_project(self,svn_path=None,env=None,tag=None):
        if svn_path is None or env is None:
            return {'status':'false','msg':'search_project: svn_path or env is None!'}
        try:
            env = env.upper()
            svn_path = svn_path.lower()
            data = {
                "page":1,
                "size":50,
                "svn_path":svn_path,
            }
            if env == "UAT": data['name'] = env
            if tag: tag = tag.upper()
            if svn_path.startswith('/'): svn_path = svn_path[1:]
            all_res = requests.get(url=self.search_url,data=json.dumps(data),headers=self.headers)
            if all_res.status_code == 200:
                all_res = all_res.json()
                if all_res['code'] == 200:
                    size = 0
                    result_list = []
                    for project_info in all_res['data']['items']:
                        project_svn = project_info['project']['svn_path']
                        _svn = '/'.join(project_svn.split('/')[3::])
                        name = project_info['project']['name']
                        _env = name.split('_')[0].upper()
                        _tag = name.split('_')[-1].upper()
                        tag_list = ['V1', 'V2', 'V3', 'V4', 'TEST']
                        if _svn == svn_path:
                            if env == "PRO" and _env == 'UAT': # PRO环境跳过UAT_开头工程
                                continue
                            if tag and _tag != tag: #传入tag参数后工程名结尾_V1/V2/V3/TEST不相等否则跳过
                                continue
                            if not tag and _tag in tag_list:
                                continue
                            if not tag and env == "PRO" and _tag == "TEST": #运营环境不传入tag:test就跳过运测
                                continue
                            size += 1
                            result_list.append(project_info)
                    if size != 0:
                        result = {'status':True,'msg':'查询完毕','data':result_list}
                    else:
                        result = {'status': False, 'msg': '未查询到此工程', 'data': result_list}
                else:
                    result = {'status':False,'msg':f'工程查询接口返回状态码 {all_res["code"]}','data':f'{all_res}'}
            else:
                result = {'status':False,'msg':f'cmdb接口返回异常状态码{all_res.status_code}','data':f'{all_res.text}'}
            return result
        except Exception as e:
            return {'status':False,'msg':'查询工程异常','data':e}

    def upgrade_project(self,id=None,version=None): #传入项目id和version版本升级
        if id is None or version is None:
            raise Exception('upgrade_project: id or version is None!')
        try:
            url = self.upgrade_url + str(id)
            data = {
                'operation': 'upgrade',
                'arg': version,
                'size': 2000,
                'page': 1,
            }
            res = requests.get(url=url,params=data,headers=self.headers)
            if res.status_code == 200:
                res_data = res.json()
                result = {'status':True,'msg':'升级工程成功','data':f'{res_data["data"]}'}
            else:
                result = {'status':False,'msg':'升级工程失败','data':f'{res.text}'}
            return result
        except Exception as e:
            return {'status':False,'msg':'升级工程报错','data':e}

    def upgrade(self, project_name=None, code_version=None, svn_path=None, svn_version=None, tag=None, env='UAT'):
        if svn_path is None or svn_version is None:
            return {'status': False,'msg':'upgrade_project: svn_path or version is None!'}

        # tag 条件过滤
        tag = '' if tag == 'v1' else tag
        real_tag = 'v1' if tag is None or tag == '' else tag

        # 返回升级的代码升级信息
        #code_data = {'svn_path': svn_path, 'svn_version': svn_version, 'tag': real_tag}
        code_data = {
            'svn_path': svn_path,
            'svn_version': svn_version,
            'tag': real_tag,
            'project_name': project_name,
            'code_version': code_version
        }

        # svn 路径结尾 prod，不升级代码，直接返回成功
        if svn_path.endswith('prod') and env == 'UAT':
            return {
                'status': True,
                'msg': f"svn 路径{svn_path} 为运营环境 svn 路径，不升级代码",
                'data': [{'project': "no_project"}],
                'code_data': code_data
            }

        # 版本号为空字符串时，不升级代码（只升级 SQL 或配置）
        if not svn_version:
            # code_data = {'svn_path': svn_path, 'svn_version': svn_version, 'tag': real_tag}
            return {
                'status': True,
                'msg': '不升级代码（升级工单只升级 SQL 或配置）',
                'data': [{'project': None}],
                'code_data': code_data
            }
        try:
            projects_info = self.search_project(svn_path=svn_path,env=env,tag=tag)
            result_list = []
            if projects_info['status']:
                status = True
                for project_data in projects_info['data']:
                    p_id = project_data['id']
                    upgrade_res = self.upgrade_project(p_id, svn_version)
                    upgrade_res = literal_eval(upgrade_res['data'])
                    i_status = upgrade_res['status']
                    if i_status != '成功': status = False
                    result_list.append(upgrade_res)
                return {
                    'status': status,
                    'msg': '升级完毕',
                    'data': result_list,
                    'code_data': code_data
                }
            else:
                return {'status':False,'msg':projects_info['msg'],'data':projects_info['data'], 'code_data': code_data}
        except Exception as err:
            return {'status':False,'msg':'升级失败','data': err.__str__(), 'code_data': code_data}

    def upgrade_v2(self, pid=None, branch=None, project_name=None, code_version=None, svn_version=None):
        branch_map = {
            'release_uat_1': 'v1',
            'release_uat_2': 'v2',
            'release_uat_3': 'v3'
        }
        v2_return_data = {
            "status": True,
            "msg": "升级成功",
            "data": {
                "svn_path": None,
                "svn_version": svn_version,
                "tag": branch_map[branch],
                "project_name": project_name,
                "code_version": code_version
            }
        }
        try:
            url = self.upgrade_v2_url + str(pid)
            data = {
                "id": pid,
                "branch": branch,
                "version": code_version,
            }
            res = requests.post(url=url, json=data, headers=self.headers)
            if res.status_code != 200:
                v2_return_data['status'] = False
            return v2_return_data
        except Exception as err:
            v2_return_data['status'] = False
            v2_return_data['msg'] = err.__str__()
            return v2_return_data

if __name__ == '__main__':
    pass
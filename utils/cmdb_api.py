import json
import requests
from ast import literal_eval
from utils.getconfig import GetYamlConfig
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

    def search_info(
            self,
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

    def search_project(
            self,
            svn_path: str = None,
            env: str = None,
            tag: str = None
    ) -> Dict[str, Union[bool, str, Dict]]:
        if svn_path is None or env is None:
            return {'status': 'false', 'msg': 'svn_path or env is None!'}
        return_data = {
            'status': False,
            'msg': '',
            'data': {}
        }
        try:
            env = env.upper()
            svn_path = svn_path.lower()
            data = {
                "page": 1,
                "size": 50,
                "svn_path": svn_path,
            }
            if env == "UAT": data['name'] = env
            if tag: tag = tag.upper()
            if svn_path.startswith('/'): svn_path = svn_path[1:]
            all_res = requests.get(url=self.search_url, data=json.dumps(data), headers=self.headers)
            if all_res.status_code == 200:
                all_res = all_res.json()
                if all_res['code'] == 200:
                    size = 0
                    tmp_list = []
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
                            tmp_list.append(project_info)
                    if size != 0:
                        return_data['status'] = True
                        return_data['msg'] = '查询工程成功'
                        return_data['data'] = tmp_list
                    else:
                        return_data['msg'] = '未查询到此工程'
                        return_data['data'] = tmp_list
                else:
                    return_data['msg'] = f'工程查询接口返回状态码 {all_res["code"]}'
                    return_data['data'] = f'{all_res}'
                    return return_data
            else:
                return_data['msg'] = f'cmdb接口返回异常状态码 {all_res.status_code}'
                return_data['data'] = f'{all_res.text}'
        except Exception as err:
            return_data['msg'] = f"查询工程异常，异常原因: {err.__str__()}"
        return return_data

    # 通过 project_name 查询 id，返回 id 用于升级
    def search_id_by_project_name(
            self,
            project_name: str = None,
            tag: str = None,
            branch: str = None,
            env: str = 'UAT'
    ) -> Dict[str, Union[bool, str, int]]:
        return_data = {
            'status': False,
            'msg': '',
            'pid': 0
        }
        try:
            # upgrade v2 接口
            if branch:
                # 拼装可用于查询用的真实 PROJECT_NAME 字段
                dash_p = project_name.upper().replace('-', '_')
                # 过滤 UAT 开头工程名
                p_name = f"{env.upper()}_{dash_p}"
                data = {
                    'page': 1,
                    'size': 50,
                    'name': p_name
                }
                # 请求接口，调整数据
                cmdb_req = requests.get(url=self.search_url, json=data, headers=self.headers)
                if cmdb_req.status_code == 200:
                    cmdb_req_json = cmdb_req.json()
                    return_data['status'] = True
                    return_data['msg'] = '查询<升级发布>工程 ID 成功'
                    return_data['pid'] = cmdb_req_json['data']['items'][0]['id']
                else:
                    return_data['msg'] = f'查询 CMDB <升级发布>接口返回非200状态, 返回数据 {cmdb_req.text}'
            # upgrade 接口
            else:
                # 拼装可用于查询用的真实 PROJECT_NAME 字段
                if tag is None or tag == 'v1' or tag == '':
                    p_name = project_name.upper().replace('-', '_')
                else:
                    p_name = project_name.upper().replace('-', '_')
                    p_name = f"{p_name}_{tag.upper()}"
                data = {
                    'page': 1,
                    'size': 50,
                    'name': p_name
                }
                # 请求接口，调整真实数据
                cmdb_req = requests.get(url=self.search_url, json=data, headers=self.headers)
                if cmdb_req.status_code == 200:
                    cmdb_req_json = cmdb_req.json()
                    project_items = cmdb_req_json['data']['items']
                    # 筛选唯一工程名值
                    project_info_list = [proj for proj in project_items if proj['project']['name'].endswith(p_name)]
                    # 过滤 UAT 开头工程名
                    project_info_list = [proj for proj in project_info_list if proj['project']['name'].startswith('UAT')]
                    return_data['status'] = True
                    return_data['msg'] = '查询<升级发布>工程 ID 成功'
                    return_data['pid'] = project_info_list[0]['id']
                else:
                    return_data['msg'] = f'查询 CMDB <升级发布>接口返回非200状态, 返回数据 {cmdb_req.text}'
        except Exception as err:
            return_data['msg'] = f'查询<升级发布>工程 ID 异常，异常原因：{err}'
        return return_data

    def upgrade_by_project_name(
            self,
            project_name: str = None,
            tag: str = None,
            branch: str = None,
            svn_path: str = None,
            svn_version: str = None,
            code_version: str = None,
            env: str = 'UAT',
    ) -> Dict[str, Union[bool, str, List, Dict]]:
        # 返回数据，兼容 v1 v2 版本的升级接口
        return_data = {
            "status": False,
            "msg": f"工程：{project_name} <升级发布> 失败",
            "data": {
                "project_name": project_name,
                "tag": tag,
                "svn_path": svn_path,
                "svn_version": svn_version,
                "code_version": code_version,
                "notice_project_name": None
            }
        }
        try:
            # 版本号为空字符串时，不升级代码（只升级 SQL 或配置）
            if not svn_version and not code_version:
                return_data['status'] = True
                return_data['msg'] = f"不升级代码（升级工单只升级 SQL 或配置）"
                # return_data['data'] = [{'project': None}]
                return return_data

            # 通过 project_name 获取<升级发布>工程真实 ID
            project_info = self.search_id_by_project_name(project_name=project_name, tag=tag, branch=branch)
            assert project_info['status'], f"工程 {project_name} 获取 CMDB <升级发布> ID 失败，失败原因：{project_info['msg']}"
            pid = project_info['pid']

            # upgrade v2 接口
            if branch:
                url = self.upgrade_v2_url + str(pid)
                upgrade_data = {
                    "id": pid,
                    "branch": branch,
                    "version": code_version,
                }
                cmdb_req = requests.post(url=url, json=upgrade_data, headers=self.headers)
            # upgrade v1 接口
            else:
                url = self.upgrade_url + str(pid)
                upgrade_data = {
                    'operation': 'upgrade',
                    'arg': svn_version,
                    'size': 2000,
                    'page': 1,
                }
                cmdb_req = requests.get(url=url, json=upgrade_data, headers=self.headers)
            # 获取请求结果，返回升级数据
            if cmdb_req.status_code == 200:
                cmdb_req_json = cmdb_req.json()
                notice_project_name = cmdb_req_json['data'].get('project', f"{project_name}")
                print(cmdb_req_json)
                return_data['status'] = True
                return_data['msg'] = f'工程：{project_name} <升级发布> 成功'
                return_data['data']['notice_project_name'] = notice_project_name
            return return_data
        except Exception as err:
            return_data['msg'] = f'调用 CMDB <升级发布> 异常，异常原因：{err.__str__()}'
        return return_data

    def upgrade(
            self,
            project_name: str = None,
            code_version: str = None,
            svn_path: str = None,
            svn_version: str = None,
            tag:str = None,
            env: str = 'UAT'
    ) -> Dict[str, Union[bool, str, List, Dict]]:
        if svn_path is None or svn_version is None:
            return {'status': False,'msg':'upgrade_project: svn_path or version is None!'}

        # tag 条件过滤
        tag = '' if tag == 'v1' else tag
        real_tag = 'v1' if tag is None or tag == '' else tag

        return_data = {
            'status': True,
            'msg': '',
            'data': {},
            # 返回升级的代码升级信息
            'code_data': {
                'svn_path': svn_path,
                'svn_version': svn_version,
                'tag': real_tag,
                'project_name': project_name,
                'code_version': code_version
            }
        }

        # svn 路径结尾 prod，不升级代码，直接返回成功
        if svn_path.endswith('prod') and env == 'UAT':
            return_data['msg'] = f"svn 路径{svn_path} 为运营环境 svn 路径，不升级代码"
            return_data['data'] = [{'project': "no_project"}]
            return return_data

        # 版本号为空字符串时，不升级代码（只升级 SQL 或配置）
        if not svn_version:
            return_data['msg'] = f"不升级代码（升级工单只升级 SQL 或配置）"
            return_data['data'] = [{'project': None}]
            return return_data

        try:
            project_info = self.search_project(svn_path=svn_path, env=env, tag=tag)
            if project_info['status']:
                tmp_list = list()
                tmp_dict = {'status': True, 'msg': '升级工程成功', 'data': ''}
                for project_data in project_info['data']:
                    # 调用 CMDB /upgrade 接口升级代码
                    p_id = project_data['id']
                    upgrade_url = self.upgrade_url + str(p_id)
                    upgrade_data = {
                        'operation': 'upgrade',
                        'arg': svn_version,
                        'size': 2000,
                        'page': 1,
                    }
                    upgrade_res = requests.get(url=upgrade_url, params=upgrade_data, headers=self.headers)
                    if upgrade_res.status_code == 200:
                        upgrade_res_json = upgrade_res.json()
                        tmp_dict['data'] = f"{upgrade_res_json['data']}"
                    else:
                        tmp_dict['status'] = False
                        tmp_dict['msg'] = f'调用 CMDB 升级工程失败'
                        tmp_dict['data'] = f'{upgrade_res.text}'
                    return_data['status'] = tmp_dict['status']
                    eval_data_dict = literal_eval(tmp_dict['data'])
                    tmp_list.append(eval_data_dict)
                return_data['msg'] = f"升级代码完成"
                return_data['data'] = tmp_list
            else:
                return_data['status'] = False
                return_data['msg'] = project_info['msg']
                return_data['data'] = project_info['data']
        except Exception as err:
            return_data['status'] = False
            return_data['msg'] = f"升级代码出现异常，异常原因: {err}"
        return return_data

    def upgrade_v2(
            self,
            project_name: str = None,
            code_version: str = None,
            svn_version: str = None,
            pid: str = None,
            branch: str = None
    ) -> Dict:
        branch_map = {
            'release_uat_1': 'v1',
            'release_uat_2': 'v2',
            'release_uat_3': 'v3'
        }
        v2_return_data = {
            "status": True,
            "msg": "<升级发布>成功",
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
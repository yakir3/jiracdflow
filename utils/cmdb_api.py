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

    # 通过 project_name 查询 id，返回工程 id 用于升级
    def search_by_project_name(
            self,
            project_name: str = None,
            tag: str = None,
            env: str = 'UAT'
    ) -> Dict[str, Union[bool, str, int]]:
        return_data = {
            'status': False,
            'msg': '',
            'pid': 0
        }
        try:
            # upgrade v2 接口
            if project_name.startswith('frontend') or project_name.startswith('backend'):
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

    def project_deploy(
            self,
            project_name: str = None,
            tag: str = 'v1',
            svn_path: str = None,
            svn_version: str = None,
            code_version: str = None,
            env: str = 'UAT',
    ) -> Dict[str, Union[bool, str, List, Dict]]:
        """
        Args:
            project_name: my-app
            tag: v1 | v2 | v3 ..
            svn_path: /svn/path
            svn_version: 1111 | a1b2c3
            code_version: a1b2c3
            env: UAT | PROD
        Returns:
            {
                'status': True,
                'msg': '工程：my-app <升级发布> 成功',
                'data': {
                    'notice_project_name': 'UAT_MY_APP_V2',
                    'project_name': 'my-app',
                    'svn_path': None,
                    'svn_version': '4472',
                    'code_version': None,
                    'tag': 'v2'
                }
            }
        """
        # # tag 为空或 null 时，强制转换为 v1 版本
        # tag = 'v1' if tag is None or tag == '' else tag
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
            },
            "notice_flags": None
        }

        # project_name 为 pro 结尾，不升级
        if project_name.endswith('pro') or project_name.endswith('prod'):
            return_data['status'] = True
            return_data['msg'] = f"工程：{project_name} 为运营工程，不处理升级"
            return_data['notice_flags'] = 'PROD_PROJECT'
            return return_data

        # 版本号为空字符串时，不升级代码（只升级 SQL 或配置）
        if not svn_version and not code_version:
            return_data['status'] = True
            return_data['msg'] = "不升级代码（升级工单只升级 SQL 或配置）"
            return_data['notice_flags'] = 'ONLY_SQL'
            return return_data

        try:
            # 通过 project_name 获取<升级发布>工程真实 ID
            project_info = self.search_by_project_name(project_name=project_name, tag=tag)
            assert project_info['status'], f"工程 {project_name} 获取 CMDB <升级发布> ID 失败，失败原因：{project_info['msg']}"
            pid = project_info['pid']

            # upgrade v2 接口
            if project_name.startswith('frontend') or project_name.startswith('backend'):
                url = self.upgrade_v2_url + str(pid)
                upgrade_data = {
                    "id": pid,
                    "branch": f'release_uat_{tag[-1]}',
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
                cmdb_req = requests.get(url=url, params=upgrade_data, headers=self.headers)
            # 获取请求结果，返回升级数据
            if cmdb_req.status_code == 200:
                cmdb_req_json = cmdb_req.json()
                notice_flags = cmdb_req_json['data'].get('project', f"{project_name}")
                return_data['status'] = True
                return_data['msg'] = f'工程：{project_name} <升级发布> 成功，版本：{code_version}，环境：{tag}'
                return_data['notice_flags'] = notice_flags
            return return_data
        except Exception as err:
            return_data['msg'] = f'调用 CMDB <升级发布> 异常，异常原因：{err.__str__()}'
        return return_data

if __name__ == '__main__':
    pass
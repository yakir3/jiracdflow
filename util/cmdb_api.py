import json
import requests
from ast import literal_eval
try:
    from getconfig import GetYamlConfig
except:
    from util.getconfig import GetYamlConfig

__all__ = ['CmdbAPI']

# 获取 JIRA 配置信息
cmdb_config = GetYamlConfig().get_config('CMDB')

class CmdbAPI():
    def __init__(self, cmdb_config=cmdb_config):
        self.search_url = cmdb_config.get('search_url')
        self.upgrade_url = cmdb_config.get('upgrade_url')
        self.domain = cmdb_config.get('domain')
        self.token = cmdb_config.get('token')
        self.headers = {
            'content-type':'application/json',
            'access-token': self.token,
        }

    def generate_project_info(self, svn_path, tag=None):
        pass

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
                    reslut_list = []
                    for project_info in all_res['data']['items']:
                        project_svn = project_info['project']['svn_path']
                        _svn = '/'.join(project_svn.split('/')[3::])
                        name = project_info['project']['name']
                        _env = name.split('_')[0].upper()
                        _tag = name.split('_')[-1].upper()
                        tag_list = ['V1','V2','V3','TEST']
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
                            reslut_list.append(project_info)
                    if size != 0:
                        result = {'status':True,'msg':'查询完毕','data':reslut_list}
                    else:
                        result = {'status': False, 'msg': '未查询到此工程', 'data': reslut_list}
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

    def upgrade(self,svn_path=None,svn_version=None,env=None,tag=None):
        # svn 路径结尾 prod，不升级代码，直接返回成功
        if svn_path.endswith('prod') and env == 'UAT':
            code_data = {'svn_path': svn_path, 'svn_version': svn_version, 'tag': tag if not None else ''}
            return {'status': True, 'msg': '运营环境 svn 路径，不升级代码', 'data': [{'project': "no_project"}], 'code_data': code_data}

        # 版本号为空字符串时，不升级代码（只升级 SQL 或配置）
        if not svn_version:
            code_data = {'svn_path': svn_path, 'svn_version': svn_version, 'tag': tag if not None else ''}
            return {'status': True, 'msg': '不升级代码（升级工单只升级 SQL 或配置）', 'data': [{'project': None}], 'code_data': code_data}

        if svn_path is None or svn_version is None or env is None:
            return {'status': False,'msg':'upgrade_project: svn_path or version or env is None!'}
        try:
            projects_info = self.search_project(svn_path=svn_path,env=env,tag=tag)
            result_list = []
            if projects_info['status']:
                status = True
                for project_data in projects_info['data']:
                    p_id = project_data['id']
                    upgrade_res = self.upgrade_project(p_id,svn_version)
                    upgrade_res = literal_eval(upgrade_res['data'])
                    i_status = upgrade_res['status']
                    if i_status != '成功': status = False
                    result_list.append(upgrade_res)
                code_data = {'svn_path': svn_path, 'svn_version': svn_version, 'tag': tag if not None else ''}
                result = {'status':status,'msg':'升级完毕','data':result_list, 'code_data': code_data}
            else:
                code_data = {'svn_path': svn_path, 'svn_version': svn_version, 'tag': tag if not None else ''}
                result = {'status':False,'msg':projects_info['msg'],'data':projects_info['data'], 'code_data': code_data}
            return result
        except Exception as e:
            code_data = {'svn_path': svn_path, 'svn_version': svn_version, 'tag': tag if not None else ''}
            return {'status':False,'msg':'升级失败','data':e, 'code_data': code_data}

if __name__ == '__main__':
    pass
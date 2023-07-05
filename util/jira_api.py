from jira import JIRA
from pprint import pprint
from typing import Union, Dict
from ast import literal_eval
try:
    from getconfig import GetYamlConfig
except:
    from util.getconfig import GetYamlConfig

__all__ = ['JiraWebhookData', 'JiraAPI']

# 获取 JIRA 配置信息
jira_config = GetYamlConfig().get_config('JIRA')

class JiraWebhookData(object):
    """
    初始化 jira webhook 请求数据，格式化为 DB serializer 格式
    customfield_10100: 配置文件
    customfield_10104: Apollo
    customfield_10103: 代码升级
    customfield_10101: 升级类型
    customfield_10200: 功能列表
    customfield_10201: SQL升级
    """
    def __init__(self, data: Dict):
        self._data = data
        # isinstance(self._data, Dict)
        self._changelog = None
        self._issue_key = None
        self._issue_id = None
        self._summary = None
        self._status = None
        self._project = None
        self._priority = None
        self._labels = None
        self._environment = None
        self._sql_info = None
        self._apollo_info = None
        self._config_info = None
        self._code_info = None
        self._webhook_event = None
        self._return_data = dict()

    def _convert_issue_data(self):
        # changelog 与 webhook_event 数据，用于流程处理
        try:
            self._changelog = self._data.get('changelog')
            self._fromstring = self._changelog['items'][0]['fromString']
            self._tostring = self._changelog['items'][0]['toString']
        except:
            self._fromstring = None
            self._tostring = None
        self._webhook_event = self._data.get('webhookEvent')

        # issue 升级数据
        self._issue = self._data.get('issue')
        self._issue_id = self._issue.get('id')
        self._issue_key = self._issue.get('key')
        self._issue_fields = self._issue.get('fields')
        self._summary = self._issue_fields.get('summary')
        self._status = self._issue_fields.get('status')['name']
        self._project = self._issue_fields.get('project')['name']
        self._priority = self._issue_fields.get('priority')['name']
        self._labels = self._issue_fields.get('labels')
        self._environment = self._issue_fields.get('environment')
        # SQL 升级信息
        self._sql_info_str = self._issue_fields.get('customfield_10201')
        self._sql_info = literal_eval(self._sql_info_str)
        # apollo 升级数据
        self._apollo_info_str = self._issue_fields.get('customfield_10104')
        self._apollo_info = literal_eval(self._apollo_info_str)
        # config 升级数据
        self._config_info_str = self._issue_fields.get('customfield_10100')
        self._config_info = literal_eval(self._config_info_str)
        # code 升级数据
        self._code_info_str = self._issue_fields.get('customfield_10103')
        self._code_info = literal_eval(self._code_info_str)

    def get_issue_data(self) -> Union[str, Dict]:
        try:
            self._convert_issue_data()
            self._return_data = {
                'fromstring': self._fromstring,
                'tostring': self._tostring,
                'issue_id': self._issue_id,
                'issue_key': self._issue_key,
                'summary': self._summary,
                'status': self._status,
                'project': self._project,
                'priority': self._priority,
                'labels': self._labels,
                'environment': self._environment,
                'sql_info': self._sql_info,
                'apollo_info': self._apollo_info,
                'config_info': self._config_info,
                'code_info': self._code_info,
                'webhook_event': self._webhook_event
            }
        except Exception as err:
            print(err)
            return f"webhook 数据解析出错，错误原因：{err.__str__()}"
        # print(self._return_data)
        return self._return_data

class JiraAPI(object):
    def __init__(self, jira_config=jira_config):
        jira_host = jira_config.get('host')
        jira_user = jira_config.get('user')
        jira_pwd  = jira_config.get('password')
        self.jira = JIRA(jira_host, auth=(jira_user,jira_pwd))

    def get_projects(self,id=None):
        if id == None:
            return self.jira.projects()
        else:
            return self.jira.project(id=id)

    def get_project_attributes(self,id):
        """
        该方法用来返回项目的详细信息。
        :param id: 项目的ID或KEY
        :return: 返回项目属性的字典
        """
        pro_dict = {}
        project = self.get_projects(id=id)
        pro_dict['id'] = project.id
        pro_dict['key'] = project.key
        pro_dict['name'] = project.name
        pro_dict['descri'] = project.description
        pro_dict['leader'] = project.lead
        pro_dict['components'] = project.components
        pro_dict['verisons'] = project.versions
        pro_dict['raw'] = project.raw   #项目的原始数据。
        return pro_dict

    def get_project_all_issue(self,id=None,issuetype=None):
        """
        :param id: 项目的id
        :param issuetype: 问题类型--这里选择故障
        :return:返回<class 'jira.client.ResultList'>,返回对象可以提取缺陷的id和key
        """
        # jql = f'project = {id} AND issuetype = {issuetype} order by created DESC'
        jql = f'project = {id} order by created DESC'
        issue_list = self.jira.search_issues(jql_str=jql, startAt=0, maxResults=False)  # 这里没有限制bug数量，所有的都可以返回回来
        return issue_list

    def get_issue_info(self, issue_id=None):
        if issue_id is None:
            return {'status':False, 'msg': 'issue_id is None!', 'data': None}
        try:
            # 问题域所有数据
            fields = self.jira.issue(id=issue_id).fields

            # 附件数据
            # attachment_data = self.get_attachment(issue_id=issue_id)
            # 获取升级数据
            sql_info_list = literal_eval(fields.customfield_10201)
            apollo_info_list = literal_eval(fields.customfield_10104)
            config_info_list = literal_eval(fields.customfield_10100)
            code_info_list = literal_eval(fields.customfield_10103)

            # 返回 issue 数据
            issue_info = {
                'issue_id': issue_id,
                'title': fields.summary,
                'status': fields.status.name,
                # 'attachment_data': attachment_data,
                'sql_info': sql_info_list,
                'apollo_info': apollo_info_list,
                'config_info': config_info_list,
                'code_info_list': code_info_list
            }
            return {'status': True, 'msg': '查询完毕', 'data': issue_info}
        except Exception as e:
            return {'status': False, 'msg': '查询失败', 'data': e}

    def get_attachment(self,issue_id=None):
        if issue_id == None:
            return {'status':False,'msg':'issue_id is None!','data':None}
        fields = self.jira.issue(id=issue_id,expand='attachment').fields
        attachments = fields.attachment
        if len(attachments) != 0:
            result_list = []
            filename_list = []
            for index in range(len(attachments)):
                file_name = attachments[index].filename
                file_info = attachments[index].get()
                result_list.append({file_name:file_info.decode()})
                filename_list.append(file_name)
            result = {'status':True,'msg':'获取附件完毕','data':result_list, 'sql_info': filename_list}
            return result
        else:
            result = {'status':False,'msg':'无附件','data':None}
            return result

    def get_transition(self,issue_id=None):
        if issue_id is None:
            return {'status':False,'msg':'issue_id is None!','data':None}
        all_res = self.jira.transitions(self.jira.issue(id=issue_id))
        result_list = []
        for transition_info in all_res:
            pprint(transition_info)
            result_list.append({'trans_id':transition_info['id'],'trans_name':transition_info['name']})
        result = {'status':True,'msg':'查询完毕','data':result_list}
        return result

    def change_transition(self,issue_id=None,change_id=None):
        if issue_id == None or change_id == None:
            return {'status':False,'msg':'issue_id or change_id is None!','data':None}
        try:
            res = self.jira.transition_issue(self.jira.issue(id=issue_id), change_id)
            return {'status':True,'msg':'变更完毕','data':''}
        except Exception as e:
            return {'status': False, 'msg': '变更失败', 'data': e}

    def issue_create(self,args=dict):
        try:
            create_data = {
                'assignee' : {'displayName': 'cdflow', 'key': 'cdflow', 'name': 'cdflow'},
                'project' : args.get('project', None),  # 项目
                'summary' : args.get('summary', None),  # 标题
                'issuetype' : {'name': args.get('issue_type', '升级')},  # 类型
                # environment = args.get('env','UAT'), #环境,由工作流控制环境信息
                'customfield_10200': "\r\n".join(args.get('function_list', "")),  # 功能列表
                'customfield_10101' : {'value': args.get('upgrade_type', '日常排版需求')},  # 升级类型
                'customfield_10201': str(args.get('sql_info', "")),  # SQL升级
                'customfield_10100': str(args.get('config_info', [])),  # 配置升级
                'customfield_10104': str(args.get('apollo_info', [])),  # Apollo升级
                'customfield_10103' : str(args.get('code_info', [])),  # 代码升级
            }
            res = self.jira.create_issue(create_data)
            return {'status':True,'msg':'jira创建问题成功','data':res}
        except Exception as e:
            return {'status':False,'msg':'jira创建问题失败','data':e}

    def issue_update(self,args=dict,issue_id=None):
        if issue_id == None:
            return {"status":False,'msg':'更新jira问题失败','data':'issue_id None！'}
        try:
            _issue = self.jira.issue(issue_id)
            update_data = {
                # 'project': args.get('project',None),  # 项目
                # 'summary': args.get('summary',None),  # 标题
                # 'issuetype': {'name': args.get('issue_type', '升级')},  # 类型
                # environment = args.get('env','UAT'), #环境,由工作流控制环境信息
                'customfield_10200': "\r\n".join(args.get('function_list', "")),  # 功能列表
                'customfield_10101': {'value': args.get('upgrade_type', '日常排版需求')},  # 升级类型
                'customfield_10201': str(args.get('sql_info', [])),  # SQL升级
                'customfield_10100': str(args.get('config_info', [])),  # 配置升级
                'customfield_10104': str(args.get('apollo_info', [])),  # Apollo升级
                'customfield_10103': str(args.get('code_info', [])),  # 代码升级
            }
            res = _issue.update(fields=update_data)
            return {'status':True,'msg':'jira更新问题成功','data': update_data}
        except Exception as e:
            return {'status':False,'msg':'jira更新问题失败','data': e}

if __name__ == '__main__':
    pass

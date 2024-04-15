from jira import JIRA
from pprint import pprint
from typing import Union, Dict
from ast import literal_eval
from utils.getconfig import GetYamlConfig

__all__ = ['JiraWebhookData', 'JiraAPI']

# 获取 JIRA 配置信息
jira_config = GetYamlConfig().get_config('JIRA')

class JiraWebhookData(object):
    """
    初始化 Jira WebHook 请求数据，格式化为 JiraIssueSerializer 序列化器格式
    customfield_11100: 功能列表
    customfield_11104: 升级类型
    customfield_11106: 是否关厅
    customfield_11108: SQL
    customfield_11109: Nacos
    customfield_11110: Config
    customfield_11112: Code
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
        # issue sql_info
        self._sql_info_str = self._issue_fields.get('customfield_10201')
        self._sql_info = literal_eval(self._sql_info_str)
        # issue apollo_info
        self._apollo_info_str = self._issue_fields.get('customfield_10104')
        self._apollo_info = literal_eval(self._apollo_info_str)
        # issue config_info
        self._config_info_str = self._issue_fields.get('customfield_10100')
        self._config_info = literal_eval(self._config_info_str)
        # issue code_info
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
                'nacos': self._nacos_info,
                'config_info': self._config_info,
                'code_info': self._code_info,
                'webhook_event': self._webhook_event
            }
        except Exception as err:
            print(err)
            return f"Jira webhook 数据解析出错，错误原因：{err.__str__()}"
        # print(self._return_data)
        return self._return_data

class JiraAPI(object):
    def __init__(self, jira_config=jira_config):
        self.jira_host = jira_config.get('host')
        self.jira_user = jira_config.get('user')
        self.jira_pwd  = jira_config.get('password')
        self.return_data = {
            'status': False,
            'msg': '',
            'data': {}
        }

    def _jira_login(self):
        self.jira = JIRA(self.jira_host, auth=(self.jira_user, self.jira_pwd))
        return self.jira

    def get_issue_info(
            self,
            issue_id: str = None
    ) -> Dict[str, Union[bool, str, Dict]]:
        jira_obj = self._jira_login()
        
        if issue_id is None:
            self.return_data['msg'] = 'issue_id is None!'
            return self.return_data
        try:
            # 问题域所有数据
            fields = jira_obj.issue(id=issue_id).fields

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
            return_data['status'] = True
            return_data['msg'] = 'Jira 工单查询完成'
            return_data['data'] = issue_info
        except Exception as err:
            return_data['msg'] = f"Jira 工单查询失败异常，异常原因: {err.__str__()}"
        return return_data

    def change_transition(
            self,
            issue_id: str = None,
            change_id: str = None
    ) -> Dict[str, str]:
        return_data = {
            'status': False,
            'msg': '',
        }
        jira_obj = self._jira_login()
        if issue_id is None or change_id is None:
            return_data['msg'] = 'issue_id or change_id is None!'
            return return_data
        try:
            res = jira_obj.transition_issue(
                jira_obj.issue(id=issue_id), change_id
            )
            return_data['status'] = True
            return_data['msg'] = f'Jira 工单变更完成, {res}'
        except Exception as err:
            return_data['msg'] = f"Jira 工单变更异常，异常原因: {err.__str__()}"
        return return_data


if __name__ == '__main__':
    pass

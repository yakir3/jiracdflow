from jira import JIRA
from typing import Union, Dict
from ast import literal_eval
from utils.getconfig import GetYamlConfig

__all__ = ['JiraWebhookData', 'JiraAPI']

class JiraWebhookData(object):
    """
    初始化 Jira WebHook 请求数据，格式化为 JiraIssueSerializer 序列化器格式
    customfield_10700: 产品 ID
    customfield_11100: 功能列表
    customfield_11104: 升级类型
    customfield_11106: 是否关厅
    customfield_11108: SQL
    customfield_11109: Nacos
    customfield_11110: Config
    customfield_11112: Code
    """
    def __init__(self, request_data: Dict):
        self.request_data = request_data
        # isinstance(self.request_data, Dict)
        self.changelog = None
        self.issue = None
        self.issue_event_type_name = None
        self.timestramp = None
        self.user = None
        self.webhook_event = None
        self.return_data = dict()

    def _convert_issue_data(self):
        # changelog 字段数据
        try:
            self.changelog = self.request_data.get('changelog')
            self.fromstring = self.changelog['items'][0]['fromString']
            self.tostring = self.changelog['items'][0]['toString']
        except Exception as err:
            self.fromstring = None
            self.tostring = None

        # issue 字段数据
        self.issue = self.request_data.get('issue')
        # issue_id issue_key 数据
        self.issue_id = self.issue.get('id')
        self.issue_key = self.issue.get('key')
        # 获取 issue_fields 数据, 通过 issue_fields 数据拿到自定义数据
        issue_fields = self.issue.get('fields')
        # issuetype 数据
        self.issue_type = issue_fields.get('issuetype').get('name')
        # jira_project 数据
        self.jira_project = issue_fields.get('project').get('name')
        # product_id 数据
        product_id_list = issue_fields.get('customfield_10700')
        self.product_id = ','.join([p.get('value') for p in product_id_list if p.get('value')])
        # summary 数据
        self.summary = issue_fields.get('summary')
        # issue_status 数据
        self.issue_status = issue_fields.get('status').get('name')
        # environment 数据
        self.environment = issue_fields.get('environment')
        # close_hall 数据
        self.close_hall = issue_fields.get('customfield_11106').get('value')
        # function_list 数据
        self.function_list = issue_fields.get('customfield_11100')
        # sql_info 数据
        self.sql_info = issue_fields.get('customfield_11108')
        # nacos_info 数据
        self.nacos_info = issue_fields.get('customfield_11109')
        # config_info 数据
        self.config_info = issue_fields.get('customfield_11110')
        # code_info 数据
        self.code_info = issue_fields.get('customfield_11112')

        # webhookEvent 字段数据
        self.webhook_event = self.request_data.get('webhookEvent')

    def get_custom_issue_data(self) -> Dict[str, Union[bool, str]]:
        return_data = {
            "status": False,
            "msg": "",
            "data": dict()
        }
        try:
            # 解析 Jira Webhook 数据
            self._convert_issue_data()
            # 返回自定义解析数据
            return_data['status'] = True
            return_data['msg'] = "Jira Webhook 解析成自定义数据成功。"
            return_data['data'] = {
                'fromstring': self.fromstring,
                'tostring': self.tostring,
                'issue_id': self.issue_id,
                'issue_key': self.issue_key,
                'jira_project': self.jira_project,
                'issue_type': self.issue_type,
                'product_id': self.product_id,
                'summary': self.summary,
                'issue_status': self.issue_status,
                'environment': self.environment,
                'close_hall': self.close_hall,
                'function_list': self.function_list,
                'sql_info': self.sql_info,
                'nacos_info': self.nacos_info,
                'config_info': self.config_info,
                'code_info': self.code_info,
                'webhook_event': self.webhook_event
            }
        except Exception as err:
            return_data['msg'] = f"Jira webhook 数据解析异常，异常原因：{err.__str__()}"
        print(return_data)
        return return_data

class JiraAPI(object):
    def __init__(
            self,
            host: str = None,
            username: str = None,
            password: str = None
    ):
        self.host = host
        self.user = username
        self._password = password

    @staticmethod
    def _login_required(func):
        def wrapper(self, *args, **kwargs):
            try:
                # 获取 JIRA 配置信息
                jira_config = GetYamlConfig().get_config('JIRA')
                self.host = jira_config.get('host')
                self.username = jira_config.get('username')
                self.password = jira_config.get('password')

                # 登录并返回 JIRA 对象
                self.jira_obj = JIRA(self.host, auth=(self.username, self.password))

                result = func(self, *args, **kwargs)
                return result
            except Exception as err:
                return_data = {
                    "status": False,
                    "msg": f"CMDB 鉴权失败，异常原因：{err.__str__()}"
                }
                return return_data
        return wrapper

    @_login_required
    def get_issue_info(
            self,
            issue_id: str = None
    ) -> Dict[str, Union[bool, str, Dict]]:
        return_data = {
            'status': False,
            'msg': '',
            'data': {}
        }

        try:
            # 问题域所有数据
            issue_obj = self.jira_obj.issue(id=issue_id)
            issue_fields = issue_obj.fields
            # 返回 issue 数据
            issue_info = {
                'issue_id': issue_id,
                'summary': issue_fields.summary,
                'issue_status': issue_fields.status.name,
                'sql_info': issue_fields.customfield_11108,
                'nacos_info': issue_fields.customfield_11109,
                'config_info': issue_fields.customfield_11110,
                'code_info': issue_fields.customfield_11112
            }
            return_data['status'] = True
            return_data['msg'] = 'Jira 工单查询成功。'
            return_data['data'] = issue_info
        except Exception as err:
            return_data['msg'] = f"Jira 工单查询失败异常，异常原因: {err.__str__()}"
        return return_data

    @_login_required
    def change_transition(
            self,
            issue_id: str = None,
            change_id: str = None
    ) -> Dict[str, Union[str, bool]]:
        """
        Args:
            issue_id: Jira IssueID or Jira IssueKey
            change_id:  Transition state name
        Returns:
            status: bool
            msg: message
        """
        return_data = {
            'status': False,
            'msg': '',
        }
        try:
            res = self.jira_obj.transition_issue(
                issue_id,
                change_id
            )
            return_data['status'] = True
            return_data['msg'] = f'Jira 工单变更成功, {res}'
        except Exception as err:
            return_data['msg'] = f"Jira 工单变更异常，异常原因: {err.__str__()}"
        return return_data


if __name__ == '__main__':
    pass

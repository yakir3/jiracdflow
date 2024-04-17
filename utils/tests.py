from django.test import TestCase
import sys
sys.path.append("..")
from pprint import pprint


# Archery
# from utils.archery_api import ArcheryAPI
# archery_obj = ArcheryAPI(main_url="https://uat-archery.opsre.net/api")
# # pprint(archery_obj.get_workflows(w_id=303))
# pprint(archery_obj.get_resource_groups())
# pprint(archery_obj.get_instances(instance_name='isagent-report'))


# CMDB
# from utils.cmdb_api import CmdbAPI
# cmdb_obj = CmdbAPI()
# pprint(cmdb_obj.search_by_project_name(project_name='backend-islot-office-api', tag='v3'))
# pprint(
#     cmdb_obj.project_deploy(
#         project_name='backend-islot-office-api',
#         tag='v3',
#         code_version='3404d8375d3b278c325a9a8ffc39219792be74ff'
#     )
# )


# from cicdflow_util import thread_upgrade
# wait_upgrade_list = [
#     {'svn_path': '/qc/rex-task-center', 'code_version': 5103, 'svn_version': 5103, 'tag': '', 'project_name': 'rex-task-center'},
#     {'svn_path': '/qc/rex-frontend-stable/prod', 'code_version': 5899, 'svn_version': 5899, 'tag': '', 'project_name': 'rex-frontend-stable-pro'}
# # ]
# upgrade_success_list = []
# upgrade_info_list = []
# upgrade_success_list, upgrade_info_list = thread_upgrade(
#     # 待升级工程数据列表
#     wait_upgrade_list,
#     # 升级完成的工程数据列表
#     upgrade_success_list,
#     # 升级完成的工程名称列表
#     upgrade_info_list
# )
# print(upgrade_success_list)
# print('======================')
# print(upgrade_info_list)


# Jira
# from utils.jira_api import JiraAPI
# jira_obj = JiraAPI()
# pprint(jira_obj.get_issue_info(issue_id=28021))
# pprint(jira_obj.change_transition('UP-7', 'ToUpgradeUAT'))
from utils.jira_api import JiraWebhookData
request_data = {'timestamp': 1713331499707, 'webhookEvent': 'jira:issue_updated', 'issue_event_type_name': 'issue_generic', 'user': {'self': 'http://jira.acclub.io/rest/api/2/user?username=Yakir', 'name': 'Yakir', 'key': 'JIRAUSER11127', 'emailAddress': 'Yakir@acclub.io', 'avatarUrls': {'48x48': 'http://jira.acclub.io/secure/useravatar?avatarId=10122', '24x24': 'http://jira.acclub.io/secure/useravatar?size=small&avatarId=10122', '16x16': 'http://jira.acclub.io/secure/useravatar?size=xsmall&avatarId=10122', '32x32': 'http://jira.acclub.io/secure/useravatar?size=medium&avatarId=10122'}, 'displayName': 'Yakir', 'active': True, 'timeZone': 'Asia/Shanghai'}, 'issue': {'id': '28021', 'self': 'http://jira.acclub.io/rest/api/2/issue/28021', 'key': 'UP-7', 'fields': {'issuetype': {'self': 'http://jira.acclub.io/rest/api/2/issuetype/10301', 'id': '10301', 'description': '', 'iconUrl': 'http://jira.acclub.io/secure/viewavatar?size=xsmall&avatarId=10310&avatarType=issuetype', 'name': '升级', 'subtask': False, 'avatarId': 10310}, 'timespent': None, 'project': {'self': 'http://jira.acclub.io/rest/api/2/project/10602', 'id': '10602', 'key': 'UP', 'name': 'UPGRADE', 'projectTypeKey': 'software', 'avatarUrls': {'48x48': 'http://jira.acclub.io/secure/projectavatar?avatarId=10324', '24x24': 'http://jira.acclub.io/secure/projectavatar?size=small&avatarId=10324', '16x16': 'http://jira.acclub.io/secure/projectavatar?size=xsmall&avatarId=10324', '32x32': 'http://jira.acclub.io/secure/projectavatar?size=medium&avatarId=10324'}}, 'customfield_10110': None, 'customfield_10111': None, 'aggregatetimespent': None, 'resolution': None, 'customfield_10113': '无', 'customfield_10114': 0.0, 'customfield_10500': None, 'customfield_10105': '0|i02wbb:', 'customfield_10700': [{'self': 'http://jira.acclub.io/rest/api/2/customFieldOption/10921', 'value': 'ISLOT', 'id': '10921', 'disabled': False}], 'customfield_10107': None, 'customfield_10108': None, 'customfield_10900': None, 'customfield_10109': None, 'resolutiondate': None, 'workratio': -1, 'lastViewed': '2024-04-17T13:24:59.693+0800', 'watches': {'self': 'http://jira.acclub.io/rest/api/2/issue/UP-7/watchers', 'watchCount': 0, 'isWatching': False}, 'created': '2024-04-11T14:52:12.000+0800', 'customfield_11110': 'add@@yakir@@backend-islot-gateway@@application.properties@@xxx@@yyy', 'priority': {'self': 'http://jira.acclub.io/rest/api/2/priority/4', 'iconUrl': 'http://jira.acclub.io/images/icons/priorities/low.svg', 'name': 'Low', 'id': '4'}, 'customfield_10100': None, 'customfield_11112': 'backend-isagent-task@@befe62db53156c601d16d7cd1de68ac0b73fcc0f', 'customfield_10101': None, 'labels': [], 'customfield_11106': {'self': 'http://jira.acclub.io/rest/api/2/customFieldOption/10916', 'value': '否', 'id': '10916', 'disabled': False}, 'customfield_11108': '01.is_admin_is01_dml_yakir.sql@@isagent-merchant@@e907469a878c7f23ca4cf42e5d13a4a528130b27', 'customfield_11109': 'add@@yakir@@job-admin.properties@@xxx@@yyy\r\nupdate@@pitt@@rex-game.properties@@update_key@@new_value\r\ndelete@@map@@gateway.properties@@delete_key@@null', 'timeestimate': None, 'aggregatetimeoriginalestimate': None, 'versions': [], 'issuelinks': [], 'assignee': {'self': 'http://jira.acclub.io/rest/api/2/user?username=cdflow', 'name': 'cdflow', 'key': 'JIRAUSER11802', 'emailAddress': 'sa@acclub.io', 'avatarUrls': {'48x48': 'http://jira.acclub.io/secure/useravatar?avatarId=10122', '24x24': 'http://jira.acclub.io/secure/useravatar?size=small&avatarId=10122', '16x16': 'http://jira.acclub.io/secure/useravatar?size=xsmall&avatarId=10122', '32x32': 'http://jira.acclub.io/secure/useravatar?size=medium&avatarId=10122'}, 'displayName': 'cdflow', 'active': True, 'timeZone': 'Asia/Shanghai'}, 'updated': '2024-04-17T13:24:59.705+0800', 'status': {'self': 'http://jira.acclub.io/rest/api/2/status/10600', 'description': '', 'iconUrl': 'http://jira.acclub.io/images/icons/status_generic.gif', 'name': 'CODE PROCESSING', 'id': '10600', 'statusCategory': {'self': 'http://jira.acclub.io/rest/api/2/statuscategory/4', 'id': 4, 'key': 'indeterminate', 'colorName': 'yellow', 'name': '处理中'}}, 'components': [], 'timeoriginalestimate': None, 'description': None, 'customfield_11100': '功能列表内容...', 'timetracking': {}, 'customfield_11104': {'self': 'http://jira.acclub.io/rest/api/2/customFieldOption/10910', 'value': '日常排版需求', 'id': '10910', 'disabled': False}, 'customfield_10600': None, 'customfield_10800': None, 'customfield_10801': None, 'aggregatetimeestimate': None, 'customfield_10802': None, 'customfield_10803': None, 'customfield_10804': None, 'summary': '【IS01】【Yakir】【TEST】20240101_1', 'creator': {'self': 'http://jira.acclub.io/rest/api/2/user?username=Yakir', 'name': 'Yakir', 'key': 'JIRAUSER11127', 'emailAddress': 'Yakir@acclub.io', 'avatarUrls': {'48x48': 'http://jira.acclub.io/secure/useravatar?avatarId=10122', '24x24': 'http://jira.acclub.io/secure/useravatar?size=small&avatarId=10122', '16x16': 'http://jira.acclub.io/secure/useravatar?size=xsmall&avatarId=10122', '32x32': 'http://jira.acclub.io/secure/useravatar?size=medium&avatarId=10122'}, 'displayName': 'Yakir', 'active': True, 'timeZone': 'Asia/Shanghai'}, 'subtasks': [], 'reporter': {'self': 'http://jira.acclub.io/rest/api/2/user?username=Yakir', 'name': 'Yakir', 'key': 'JIRAUSER11127', 'emailAddress': 'Yakir@acclub.io', 'avatarUrls': {'48x48': 'http://jira.acclub.io/secure/useravatar?avatarId=10122', '24x24': 'http://jira.acclub.io/secure/useravatar?size=small&avatarId=10122', '16x16': 'http://jira.acclub.io/secure/useravatar?size=xsmall&avatarId=10122', '32x32': 'http://jira.acclub.io/secure/useravatar?size=medium&avatarId=10122'}, 'displayName': 'Yakir', 'active': True, 'timeZone': 'Asia/Shanghai'}, 'customfield_10120': [{'self': 'http://jira.acclub.io/rest/api/2/user?username=cdflow', 'name': 'cdflow', 'key': 'JIRAUSER11802', 'emailAddress': 'sa@acclub.io', 'avatarUrls': {'48x48': 'http://jira.acclub.io/secure/useravatar?avatarId=10122', '24x24': 'http://jira.acclub.io/secure/useravatar?size=small&avatarId=10122', '16x16': 'http://jira.acclub.io/secure/useravatar?size=xsmall&avatarId=10122', '32x32': 'http://jira.acclub.io/secure/useravatar?size=medium&avatarId=10122'}, 'displayName': 'cdflow', 'active': True, 'timeZone': 'Asia/Shanghai'}], 'customfield_10000': '{summaryBean=com.atlassian.jira.plugin.devstatus.rest.SummaryBean@12fbcaf7[summary={pullrequest=com.atlassian.jira.plugin.devstatus.rest.SummaryItemBean@16946e8[overall=PullRequestOverallBean{stateCount=0, state=\'OPEN\', details=PullRequestOverallDetails{openCount=0, mergedCount=0, declinedCount=0}},byInstanceType={}], build=com.atlassian.jira.plugin.devstatus.rest.SummaryItemBean@37457333[overall=com.atlassian.jira.plugin.devstatus.summary.beans.BuildOverallBean@7c503d35[failedBuildCount=0,successfulBuildCount=0,unknownBuildCount=0,count=0,lastUpdated=<null>,lastUpdatedTimestamp=<null>],byInstanceType={}], review=com.atlassian.jira.plugin.devstatus.rest.SummaryItemBean@4cc9f379[overall=com.atlassian.jira.plugin.devstatus.summary.beans.ReviewsOverallBean@1a2c7b80[stateCount=0,state=<null>,dueDate=<null>,overDue=false,count=0,lastUpdated=<null>,lastUpdatedTimestamp=<null>],byInstanceType={}], deployment-environment=com.atlassian.jira.plugin.devstatus.rest.SummaryItemBean@66c4f1d[overall=com.atlassian.jira.plugin.devstatus.summary.beans.DeploymentOverallBean@7ba87370[topEnvironments=[],showProjects=false,successfulCount=0,count=0,lastUpdated=<null>,lastUpdatedTimestamp=<null>],byInstanceType={}], repository=com.atlassian.jira.plugin.devstatus.rest.SummaryItemBean@78790547[overall=com.atlassian.jira.plugin.devstatus.summary.beans.CommitOverallBean@1f081b3[count=0,lastUpdated=<null>,lastUpdatedTimestamp=<null>],byInstanceType={}], branch=com.atlassian.jira.plugin.devstatus.rest.SummaryItemBean@65003237[overall=com.atlassian.jira.plugin.devstatus.summary.beans.BranchOverallBean@5d8bee14[count=0,lastUpdated=<null>,lastUpdatedTimestamp=<null>],byInstanceType={}]},errors=[],configErrors=[]], devSummaryJson={"cachedValue":{"errors":[],"configErrors":[],"summary":{"pullrequest":{"overall":{"count":0,"lastUpdated":null,"stateCount":0,"state":"OPEN","details":{"openCount":0,"mergedCount":0,"declinedCount":0,"total":0},"open":true},"byInstanceType":{}},"build":{"overall":{"count":0,"lastUpdated":null,"failedBuildCount":0,"successfulBuildCount":0,"unknownBuildCount":0},"byInstanceType":{}},"review":{"overall":{"count":0,"lastUpdated":null,"stateCount":0,"state":null,"dueDate":null,"overDue":false,"completed":false},"byInstanceType":{}},"deployment-environment":{"overall":{"count":0,"lastUpdated":null,"topEnvironments":[],"showProjects":false,"successfulCount":0},"byInstanceType":{}},"repository":{"overall":{"count":0,"lastUpdated":null},"byInstanceType":{}},"branch":{"overall":{"count":0,"lastUpdated":null},"byInstanceType":{}}}},"isStale":false}}', 'customfield_10121': None, 'aggregateprogress': {'progress': 0, 'total': 0}, 'customfield_10122': None, 'customfield_10123': None, 'customfield_10201': [], 'customfield_10124': None, 'customfield_10202': None, 'customfield_10400': None, 'customfield_10115': None, 'environment': 'UAT', 'customfield_10117': None, 'customfield_10118': None, 'progress': {'progress': 0, 'total': 0}, 'comment': {'comments': [], 'maxResults': 0, 'total': 0, 'startAt': 0}, 'votes': {'self': 'http://jira.acclub.io/rest/api/2/issue/UP-7/votes', 'votes': 0, 'hasVoted': False}, 'worklog': {'startAt': 0, 'maxResults': 20, 'total': 0, 'worklogs': []}}}, 'changelog': {'id': '302650', 'items': [{'field': 'status', 'fieldtype': 'jira', 'from': '10601', 'fromString': 'CONFIG PROCESSING', 'to': '10600', 'toString': 'CODE PROCESSING'}]}}
jira_event_webhook_obj = JiraWebhookData(request_data)
res = jira_event_webhook_obj.get_custom_issue_data()
print(res)
print(jira_event_webhook_obj.webhook_event)


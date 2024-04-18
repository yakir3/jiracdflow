from django.test import TestCase
import sys
sys.path.append("..")
from pprint import pprint


# Archery
# from utils.archery_api import ArcheryAPI
# archery_obj = ArcheryAPI(main_url="https://uat-archery.opsre.net/api")
# # pprint(archery_obj.get_workflows(w_id=303))
# pprint(archery_obj.get_resource_groups())
# pprint(archery_obj.get_instances(instance_name="isagent-report"))


# CMDB
# from utils.cmdb_api import CmdbAPI
# cmdb_obj = CmdbAPI()
# pprint(cmdb_obj.search_by_project_name(project_name="backend-islot-office-api", tag="v3"))
# pprint(
#     cmdb_obj.project_deploy(
#         project_name="backend-islot-office-api",
#         tag="v3",
#         code_version="3404d8375d3b278c325a9a8ffc39219792be74ff"
#     )
# )


# from cicdflow_util import thread_upgrade
# wait_upgrade_list = [
#     {"svn_path": "/qc/rex-task-center", "code_version": 5103, "svn_version": 5103, "tag": "", "project_name": "rex-task-center"},
#     {"svn_path": "/qc/rex-frontend-stable/prod", "code_version": 5899, "svn_version": 5899, "tag": "", "project_name": "rex-frontend-stable-pro"}
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
# print("======================")
# print(upgrade_info_list)


# Jira
# from utils.jira_api import JiraAPI
# jira_obj = JiraAPI()
# pprint(jira_obj.get_issue_info(issue_id=28021))
# pprint(jira_obj.change_transition("UP-7", "ToUpgradeUAT"))
from utils.jira_api import JiraWebhookData
request_data = {}
jira_event_webhook_obj = JiraWebhookData(request_data)
res = jira_event_webhook_obj.get_custom_issue_data()
print(res)
print(jira_event_webhook_obj.webhook_event)


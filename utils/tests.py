from django.test import TestCase
import sys
sys.path.append("..")
from utils.getconfig import GetYamlConfig
from pprint import pprint


# Archery
from utils.archery_api import ArcheryAPI
archery_config = GetYamlConfig().get_config("Archery")
assert archery_config, "获取 Archery 配置信息失败，检查 config.yaml 配置文件。"
archery_host = archery_config.get("uat_host")
archery_obj = ArcheryAPI(
    host=archery_host,
    username=archery_config.get("username"),
    password=archery_config.get("password")
)
# pprint(archery_obj.get_workflows(w_id=303))
pprint(archery_obj.get_resource_groups())
# pprint(archery_obj.get_instances(instance_name="isagent-report"))



# CMDB
# from utils.cmdb_api import CmdbAPI
# cmdb_config = GetYamlConfig().get_config("CMDB")
# assert cmdb_config, f"获取 CMDB 配置信息失败，检查 config.yaml 配置文件。"
# cmdb_host = cmdb_config.get('host')
# cmdb_token = cmdb_config.get('token')
# # 创建 CMDB 对象
# cmdb_obj = CmdbAPI(
#     host=cmdb_host,
#     token=cmdb_token
# )
# pprint(cmdb_obj.search_by_project_name(project_name="backend-islot-office-api", tag="v3"))
# pprint(
#     cmdb_obj.project_deploy(
#         project_name="backend-islot-office-api",
#         tag="v3",
#         code_version="eb8cd06297fa57c58b5b77e8a967fd3c0b92a752"
#     )
# )


# Jira
# from utils.jira_api import JiraAPI
# jira_obj = JiraAPI()
# pprint(jira_obj.get_issue_info(issue_id=28021))
# pprint(jira_obj.change_transition("UP-7", "ToUpgradeUAT"))
# from utils.jira_api import JiraWebhookData
# request_data = {}
# jira_event_webhook_obj = JiraWebhookData(request_data)
# res = jira_event_webhook_obj.get_custom_issue_data()
# print(res)
# print(jira_event_webhook_obj.webhook_event)


# cicdflow_utils.py
# from cicdflow_utils import *
# sql_info = "isagent_isagent-merchant@@01.is01_ddl_yakir.sql@@03fd9df8dc14fd1ce645193423a04c369d57181c\r\nisagent_isagent-merchant@@02.is01_ddl_yakir.sql@@03fd9df8dc14fd1ce645193423a04c369d57181c\r\nisagent_isagent-merchant@@01.is01_dml_yakir.sql@@03fd9df8dc14fd1ce645193423a04c369d57181c"
# pprint(format_sql_info(sql_info))
# nacos_info = "map-test.propertles@@add@@map-testkey@@map-testvalue\r\nmap-test-2.propertles@@update@@server.dns@@1.1.1.1\r\nmap-test-2.propertles@@delete@@need_delete_key"
# # pprint(format_nacos_info(nacos_info))
# print(nacos_handle(
#     nacos_info=nacos_info,
#     product_id='ISLOT',
#     environment='UAT'
# ))
# code_info = "backend-islot-api-gci@@346f5638a670e06a72c22d7bbcea5a4498da8113@@v4\r\nbackend-islot-api-report@@a41557a52ee242000baf42ca5a6658eab5b97929@@v4"
# print(format_code_info(code_info=code_info, environment="UAT"))




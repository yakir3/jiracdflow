from django.test import TestCase
import sys
sys.path.append("..")
from utils.getconfig import GetYamlConfig
from pprint import pprint


# Archery
# from utils.archery_api import ArcheryAPI
# archery_config = GetYamlConfig().get_config("Archery")
# assert archery_config, "获取 Archery 配置信息失败，检查 config.yaml 配置文件。"
# archery_host = archery_config.get("uat_host")
# archery_obj = ArcheryAPI(
#     host=archery_host,
#     username=archery_config.get("username"),
#     password=archery_config.get("password")
# )
# pprint(archery_obj.get_workflows(w_id=303))
# pprint(archery_obj.get_resource_groups())
# pprint(archery_obj.get_instances(instance_name="isagent-report"))



# CMDB
# from utils.cmdb_api import CmdbAPI
# cmdb_config = GetYamlConfig().get_config("CMDB")
# assert cmdb_config, f"获取 CMDB 配置信息失败，检查 config.yaml 配置文件。"
# cmdb_host = cmdb_config.get("host")
# cmdb_token = cmdb_config.get("token")
# cmdb_vmc_host = cmdb_config.get("UAT").get("ISLOT-AGENT").get("vmc_host")
# # 创建 CMDB 对象
# cmdb_obj = CmdbAPI(
#     host=cmdb_host,
#     token=cmdb_token
# )
# pprint(
#     cmdb_obj.search_by_project_name(
#         service_name="frontend-isagent-web",
#         environment="UAT",
#         vmc_host=cmdb_vmc_host
#     )
# )
# pprint(
#     cmdb_obj.project_deploy(
#         service_name="backend-islot-api-gci",
#         code_version="346f5638a670e06a72c22d7bbcea5a4498da8113",
#         branch="release_uat_4",
#         environment="UAT",
#         vmc_host=cmdb_vmc_host
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

# python manage.py shell
# from utils.tests import yakir_test
# yakir_test()
def yakir_test():
    from utils.cicdflow_utils import format_code_info, compare_list_info, thread_code_handle
    last_code_info = None
    current_code_info = "backend-islot-api-gci@@346f5638a670e06a72c22d7bbcea5a4498da8113@@release_uat_4\r\nbackend-islot-api-report@@a41557a52ee242000baf42ca5a6658eab5b97929@@release_uat_4"
    last_code_info_list = format_code_info(code_info=last_code_info, environment="UAT")
    current_code_info_list = format_code_info(code_info=current_code_info, environment="UAT")
    print(last_code_info_list, current_code_info_list)
    print(compare_list_info(last_code_info_list, current_code_info_list))
    # pprint(
    #     thread_code_handle(
    #         last_code_info=last_code_info,
    #         current_code_info=current_code_info,
    #         product_id="ISLOT",
    #         environment="UAT",
    #         issue_key="UP-20"
    #     )
    # )
yakir_test()




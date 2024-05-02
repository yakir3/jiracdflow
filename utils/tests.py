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
# pprint(archery_obj.get_workflow(w_id=303))
# pprint(archery_obj.get_resource_group(resource_name="islot"))
# pprint(archery_obj.get_instance(instance_name="islot-main"))
# pprint(archery_obj.get_instance(instance_name="islot-v2"))
# pprint(archery_obj.get_instance(instance_name="islot-v3"))
# pprint(archery_obj.get_instance(instance_name="islot-v4"))
# pprint(archery_obj.commit_workflow(
#     sql_index=0,
#     sql_filename="yakir-test",
#     sql_release_info="manual",
#     sql_content="select 1;",
#     workflow_name="yakir-test",
#     demand_url="yakir-test",
#     resource_name="islot",
#     instance_name="islot-v3",
#     db_name=None,
#     is_backup=False,
#     engineer="cdflow"
# ))



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


# Gitlab
# from gitlab_api import get_sql_content
# gitlab_config = GetYamlConfig().get_config('Gitlab')
# assert gitlab_config, "获取 Gitlab 配置信息失败，检查 config.yaml 配置文件。"
# gitlab_host = gitlab_config.get("host")
# gitlab_token = gitlab_config.get("private_token")
# gitlab_project_id_dict = gitlab_config.get("reponame_map_id")
# repo_name="isagent_pg-dbtest"
# sql_content = get_sql_content(
#     server_address=gitlab_host,
#     private_token=gitlab_token,
#     file_name="01.dbtest_dml_yakir.sql",
#     commit_sha="9f871e44a1b3b332b05c2d6c4d3bc4b420dee74d",
#     project_id=gitlab_project_id_dict.get(repo_name)
# )
# print(sql_content)


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



# python manage.py shell
# from utils.tests import yakir_test
# yakir_test()
def yakir_test():
    from utils.cicdflow_utils import format_sql_info, sql_submit_handle
    sql_info = "isagent_pg-dbtest@@01.dbtest_ddl_yakir.sql@@9f871e44a1b3b332b05c2d6c4d3bc4b420dee74d\r\nisagent_pg-dbtest@@01.dbtest_dml_yakir.sql@@9f871e44a1b3b332b05c2d6c4d3bc4b420dee74d\r\nisagent_pg-dbtest@@02.dbtest_dml_yakir.sql@@9f871e44a1b3b332b05c2d6c4d3bc4b420dee74d"
    sql_info_list = format_sql_info(sql_info)
    print(sql_submit_handle(
        sql_info_list=sql_info_list,
        workflow_name="yakir-test-xxxxx",
        environment="UAT"
    ))

    # nacos_info = "map-test.propertles@@add@@yakir-add@@yakir-value\r\nmap-test.propertles@@update@@need_update@@2.2"
    # nacos_info_dict = format_nacos_info(nacos_info)
    # print(nacos_handle(
    #     nacos_info_dict=nacos_info_dict,
    #     product_id='ISLOT',
    #     environment='UAT'
    # ))

    # last_code_info = None
    # current_code_info = "backend-islot-api-gci@@346f5638a670e06a72c22d7bbcea5a4498da8113@@release_uat_4\r\nbackend-islot-api-report@@a41557a52ee242000baf42ca5a6658eab5b97929@@release_uat_4"
    # last_code_info_list = format_code_info(code_info=last_code_info, environment="UAT")
    # current_code_info_list = format_code_info(code_info=current_code_info, environment="UAT")
    # pprint(
    #     thread_code_handle(
    #         last_code_info=last_code_info,
    #         current_code_info=current_code_info,
    #         product_id="ISLOT",
    #         environment="UAT",
    #         issue_key="UP-20"
    #     )
    # )



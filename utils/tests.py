from django.test import TestCase
import sys
sys.path.append("..")
from pprint import pprint

# Archery
# from utils.archery_api import ArcheryAPI
# archery_obj = ArcheryAPI()
# pprint(archery_obj.get_resource_groups())
# pprint(archery_obj.get_instances(instance_name='isagent-report'))
# pprint(archery_obj.get_workflows(w_id=303))

# CMDB
from utils.cmdb_api import CmdbAPI
cmdb_obj = CmdbAPI()
# code_data = {'svn_path': '/qc/rex-user-center', 'code_version': 5719, 'svn_version': 5719, 'tag': 'v2', 'project_name': 'rex-user-center'}
# code_data = {'svn_path': '/qc/rex-task-center', 'code_version': 5103, 'svn_version': 5103, 'tag': 'v4', 'project_name': 'rex-task-center'}
# pprint(cmdb_obj.upgrade(**code_data))
# pprint(cmdb_obj.search_by_project_name(project_name='rex-admin-web', tag='v1'))
pprint(cmdb_obj.search_by_project_name(project_name='frontend-test-xxx', tag='v2'))
# pprint(cmdb_obj.search_by_project_name(project_name='frontend-isagent-web', tag='v2'))
# pprint(
#     cmdb_obj.upgrade_by_project_name(
#         project_name='rex-admin',
#         tag='v2',
#         svn_version='4472',
#         code_version=None
#     )
# )
# pprint(
#     cmdb_obj.project_deploy(
#         project_name='frontend-test-xxx',
#         tag='',
#         svn_path=None,
#         svn_version='xxx111',
#         code_version='xxx111'
#     )
# )

# from cicdflow_util import thread_upgrade
# wait_upgrade_list = [
#     {'svn_path': '/qc/rex-task-center', 'code_version': 5103, 'svn_version': 5103, 'tag': '', 'project_name': 'rex-task-center'},
#     {'svn_path': '/qc/rex-frontend-stable/prod', 'code_version': 5899, 'svn_version': 5899, 'tag': '', 'project_name': 'rex-frontend-stable-pro'}
# ]
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
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
code_data = {'svn_path': '/qc/rex-task-center', 'code_version': 5103, 'svn_version': 5103, 'tag': 'v4', 'project_name': 'rex-task-center'}
pprint(cmdb_obj.upgrade(**code_data))
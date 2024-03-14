from django.test import TestCase
import sys
sys.path.append("..")
from pprint import pprint

# Archery
from utils.archery_api import ArcheryAPI
archery_ins = ArcheryAPI()
# pprint(archery_ins.get_resource_groups())
# pprint(archery_ins.get_instances(instance_name='isagent-report'))
pprint(archery_ins.get_workflows(w_id=303))
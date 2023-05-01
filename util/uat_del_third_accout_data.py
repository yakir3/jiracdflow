#!/opt/py-project/devops_tools/venv/bin/python
import sys
import time
from ast import literal_eval

sys.path.append("..")
from typing import Dict, List, Union, Any

from util.archery_api import ArcheryAPI
archery_obj = ArcheryAPI()

# Archery 交互操作：按顺序提交、审核、执行 工单
def uat_delete_account_data(
        # 待删除用户字符串
        username_str: str = None,
        workflow_name: str = 'UAT_QC_删除第三方测试账号数据',
        resource_tag: str = 'QC',
        # instance_tag: str = 'uat_pg_env'
        instance_tag: str = 'qc-merchant'
    ) -> Union[Dict, str]:
    try:
        # 生成删除 sql 语句
#         delete_sql_content = f"""DELETE FROM stu
# where stu.name in ({username_str});
#
# DELETE FROM stu
# where stu.name in ({username_str});
# """
        delete_sql_content = f"""DELETE FROM r_customer_third_info cti
WHERE cti.merchant_id = 'QC' and cti.customer_id IN (select rc.customer_id  from r_customer rc where rc.merchant_id = 'QC' and rc.login_name in ({username_str}));

DELETE FROM r_customer_balance rcb
WHERE rcb.merchant_id = 'QC' and rcb.customer_id IN (select rc.customer_id  from r_customer rc where rc.merchant_id = 'QC' and rc.login_name in ({username_str}));

DELETE FROM r_customer_ext rce
WHERE rce.merchant_id = 'QC' and rce.login_name IN ({username_str});

DELETE FROM r_customer_phone_record rcpr
WHERE rcpr.merchant_id = 'QC' and rcpr.login_name IN ({username_str});

DELETE FROM r_customer_email_record rcer
WHERE rcer.merchant_id = 'QC' and rcer.login_name IN ({username_str});

DELETE FROM r_customer rc
WHERE rc.merchant_id = 'QC' and rc.login_name IN ({username_str});
"""

        # 提交工单
        commit_data = {
            'sql': delete_sql_content,
            'workflow_name': workflow_name,
            'resource_tag': resource_tag,
            'instance_tag': instance_tag
        }
        commit_res = archery_obj.commit_workflow(commit_data)
        # 提交工单失败直接返回，不继续审核 & 执行流程
        if not commit_res['status']:
            return commit_res
        wid = commit_res['data']['w_id']

        # 审核工单，审核失败退出
        audit_res = archery_obj.audit_workflow(workflow_id=wid)
        if not audit_res['status']:
            return audit_res

        # 执行工单，执行失败退出
        execute_res = archery_obj.execute_workflow(workflow_id=wid)
        if not execute_res['status']:
            return execute_res
        # 等待10s SQL 工单执行完成，状态变化为成功
        time.sleep(10)

        # 审核 & 执行都无出错，查询工单结果，返回数据
        select_res = archery_obj.get_workflows(args={'id': wid})
        if not select_res['status']:
            return select_res

        # 获取成功工单的执行结果，返回执行文本数据
        execute_msg = "------------------QC_BEGIN-----------------\n"
        execute_result = select_res['data'][0]['execute_result']
        for i in execute_result:
            sql_content = i['sql']
            affected_rows = i['affected_rows']
            execute_time = i['execute_time']
            execute_msg += f"执行 SQL 语句：{sql_content}; \n影响行数：{affected_rows}，执行时间：{execute_time}\n\n"
        execute_msg += "------------------QC_END-----------------"
        return execute_msg

    except Exception as err:
        return_data = {'status': False, 'msg': f'删除数据过程出现异常，异常原因：{err.__str__()}'}
        return return_data

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("未输入 users 参数，请确认！！！")
        sys.exit(111)
    jenkins_user_parameter = sys.argv[1]
    if not jenkins_user_parameter:
        print('users 参数不允许为空或 None，请确认！！！')
    user_str = ", ".join("'" + item + "'" for item in jenkins_user_parameter.split(','))
    # 处理逻辑函数
    res = uat_delete_account_data(user_str)
    print(res)
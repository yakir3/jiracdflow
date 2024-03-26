#!/opt/py-project/jiracdflow/venv/bin/python
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
        merchant_id: str = None,
        instance_tag: str = None,
        workflow_name: str = 'UAT_QC_删除第三方测试账号数据',
        resource_tag: str = 'QC',
        db_name: str = 'bwupxx'
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
WHERE cti.merchant_id = '{merchant_id}' and cti.customer_id IN (select rc.customer_id  from r_customer rc where rc.merchant_id = '{merchant_id}' and rc.login_name in ({username_str}));

DELETE FROM r_customer_balance rcb
WHERE rcb.merchant_id = '{merchant_id}' and rcb.customer_id IN (select rc.customer_id  from r_customer rc where rc.merchant_id = '{merchant_id}' and rc.login_name in ({username_str}));

DELETE FROM r_customer_ext rce
WHERE rce.merchant_id = '{merchant_id}' and rce.login_name IN ({username_str});

DELETE FROM r_customer_phone_record rcpr
WHERE rcpr.merchant_id = '{merchant_id}' and rcpr.login_name IN ({username_str});

DELETE FROM r_customer_email_record rcer
WHERE rcer.merchant_id = '{merchant_id}' and rcer.login_name IN ({username_str});

DELETE FROM r_customer rc
WHERE rc.merchant_id = '{merchant_id}' and rc.login_name IN ({username_str});
"""
        # 提交工单
        commit_data = {
            'sql_content': delete_sql_content,
            'workflow_name': workflow_name,
            'resource_tag': resource_tag,
            'instance_tag': instance_tag,
            'db_name': db_name
        }
        commit_res = archery_obj.commit_workflow(**commit_data)
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

        # # 审核 & 执行都无出错，查询工单结果，返回数据
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

def uat_truncate_agent(
        # 待删除用户字符串
        instance_tag: str = None,
        workflow_name: str = 'UAT_QC_删除代理佣金数据',
        resource_tag: str = 'QC',
        db_name: str = 'bwupxx'
) -> Union[Dict, str]:
    try:
        delete_sql_content = f"""
-- 删除CPA
truncate table r_agent_cpa_record;
-- 删除负盈利
truncate table r_agent_settlement_record;
-- 删除负盈利详情
truncate table r_agent_settlement_detail;
-- 删除扶持金
truncate table r_agent_aid_config;
-- 删除扶持金申请记录
truncate table r_agent_aid_record;
-- 删除扶持金申请记录
truncate table r_settlement_first_deposit_record;
-- 删除输赢详情
truncate table r_agent_lobby_record;
-- 删除输赢详情
truncate table r_agent_cpa_commission_details;
truncate table r_agent_arrears_record;
-- 还原欠款（代理欠平台的）
update r_agent_ext_config set cpa_remaining_amount = 0 where id != 1;
"""
        # 提交工单
        commit_data = {
            'sql_content': delete_sql_content,
            'workflow_name': workflow_name,
            'resource_tag': resource_tag,
            'instance_tag': instance_tag,
            'db_name': db_name
        }
        commit_res = archery_obj.commit_workflow(**commit_data)
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

        # # 审核 & 执行都无出错，查询工单结果，返回数据
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
        print("Usage: ./uat_db_operate.py OPERATE(uat_delete_account_data|uat_truncate_agent) USERS(u1[,u2,u3]) MERCHANT_ID(QC|B01|RS8)")
        sys.exit(0)

    # 获取操作方式
    operate = sys.argv[1]
    # 获取删除的用户和产品参数
    jenkins_user_parameter = sys.argv[2]
    merchant_id_parameter = sys.argv[3]
    # 判断产品是否在已有产品内，符合要求传入 merchant_id
    merchant_id_dict = {
        'QC': 'qc-merchant',
        'B01': 'b01-merchant',
        'RS8': 'rs8-merchant',
        'FPB': 'fpb-merchant',
        'PSL': 'psl-merchant'
    }
    db_name_dict = {
        'QC': 'bwup01',
        'B01': 'bwup03',
        'RS8': 'bwup04',
        'FPB': 'bwup99',
        'PSL': 'bwup99'
    }
    if merchant_id_parameter not in merchant_id_dict.keys():
        print('product 参数不在当前已有的产品列表中，请确认！！！')
        sys.exit(111)
    instance_tag = merchant_id_dict[merchant_id_parameter]
    db_name = db_name_dict[merchant_id_parameter]

    # 删除第三方测试账号
    if operate == 'uat_delete_account_data':
        # 判断用户参数条件，符合要求生成用户字符串，已逗号分隔
        if not jenkins_user_parameter:
            print('users 参数不允许为空或 None，请确认！！！')
            sys.exit(111)
        user_str = ", ".join("'" + item + "'" for item in jenkins_user_parameter.split(','))
        # 处理逻辑函数
        res = uat_delete_account_data(user_str, merchant_id_parameter, instance_tag=instance_tag, db_name=db_name)
        print(res)
    # 删除代理后台佣金数据
    elif operate == 'uat_truncate_agent':
        res = uat_truncate_agent(instance_tag=instance_tag, db_name=db_name)
        print(res)
    else:
        print('未允许的操作，请重试!')
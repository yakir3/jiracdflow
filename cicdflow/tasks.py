from celery import shared_task
from datetime import timedelta
import json
from django.core.exceptions import ObjectDoesNotExist

from cicdflow.models import CICDState
from cicdflow.views import d_logger
from util.archery_operate import ArcheryAPI, archery_config
from util.svn_client import SvnClient
from util.redis_client import RedisClient

""""
定时获取所有 SQL 状态 2 & 3 的工作流
  状态为3时：提交 SQL 工单到 Archery，待 DBA 审核执行，并将状态置为2
  状态为2时：调用 Archery 接口获取 SQL 工单执行结果
    -> 成功置为0
    -> 失败置为1
  状态为0/1/9时：忽略/发出通知？
"""
@shared_task
def sqlstate_task() -> None:
    # 初始化实例
    redis_client = RedisClient().redis_client
    archery_api = ArcheryAPI()
    schema = archery_config['schema']

    # 获取当前 sql_state 为 3 的待执行工作流，轮训每个工作流提交 SQL 工单
    waiting_execute = CICDState.objects.filter(flow_state=3, sql_state=3)
    for i in range(len(waiting_execute)):
        try:
            we_ins = waiting_execute.get(id=waiting_execute.values()[i]['id'])
            # 已邮件标题作为 key 唯一值，每个 value 为 dict ，key 为 workflow_name 唯一值
            email_title = we_ins.email_title.email_title
            # 不存在 redis key，首次提交 SQL 工单
            # 失败工单存入 redis 队列，重复执行时只继续提交失败工单，直到所有工单成功将 sql_state 置为 2
            if not redis_client.llen(email_title):
                # 获取提交 SQL 工单所需参数
                archery_data_list = []
                run_date_start = we_ins.update_date.strftime('%Y-%m-%dT%H:%M:%S')
                run_date_end = (we_ins.update_date + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%S')
                sql_info_list = we_ins.email_title.sql_info
                for sql_info in sql_info_list:
                    svn_path = sql_info['svn_path'].replace('10.138.200.100', '172.20.5.112')
                    svn_sub_path = svn_path.split('/')[-1]
                    svn_version = sql_info['svn_version']
                    svn_file_name = sql_info['svn_file']

                    workflow_name = f"{email_title}-{svn_version}-{svn_file_name.split('.')[0]}"
                    # 根据 svn 路径判断是否提交工单，只提交当前 Archery 已有的 DB 实例
                    try:
                        schema_info = schema[svn_sub_path]
                        group_id = schema_info['group_id']
                        instance_id = schema_info['instance_id']
                        db_name = schema_info['db_name']
                    except KeyError:
                        d_logger.info(f"升级邮件： <{email_title}> ，SQL 工单：{workflow_name} DB 不存在于当前 Archery 已有实例，库名：<{svn_sub_path}>")
                        continue
                    svn_obj = SvnClient(svn_path)
                    sql_content_value = svn_obj.get_file_content(revision=svn_version, filename=svn_file_name)
                    tmp_data = (workflow_name, group_id, instance_id, db_name, sql_content_value)
                    archery_data_list.append(tmp_data)

                # 调用 ArcheryAPI 实例方法，提交 SQL 工单
                assert archery_data_list, f"升级邮件： <{email_title}> 所有 SQL DB 都不存在于当前 Archery 已有实例，不提交 Archery，人工处理 SQL"
                for archery_data in archery_data_list:
                    workflow_data = {
                        'workflow_name': archery_data[0],
                        'demand_url': archery_data[0],
                        'group_id': archery_data[1],
                        'instance_id': archery_data[2],
                        'db_name': archery_data[3],
                        'run_date_start': run_date_start,
                        'run_date_end': run_date_end,
                        'sql_content': archery_data[4]
                    }
                    submit_result = archery_api.submit_sql_ticket(**workflow_data)
                    # 提交失败的 SQL 工单存入 redis 队列
                    if not submit_result['code']:
                        print(f"升级邮件： <{email_title}> ，SQL 工单：{workflow_name} 提交成功。响应消息：{submit_result['msg']}")
                    else:
                        print(f"升级邮件： <{email_title}> ，SQL 工单：{workflow_name} 提交失败。响应消息：{submit_result['msg']}")
                        redis_client.rpush(email_title, json.dumps(workflow_data))
                # redis 队列为空，所有待执行 SQL 工单都提交成功，sql_state 状态置为2
                if not redis_client.llen(email_title):
                    redis_client.delete(email_title)
                    we_ins.sql_state = 2
                    we_ins.save()
            # 存在 redis key，有失败 SQL 工单。获取 redis 队列中所有元素重新提交，提交成功删除队列数据，提交失败将数据放回队列待下次定时任务执行
            else:
                for i in range(redis_client.llen(email_title)):
                    # 重复提交失败的 SQL 工单，如提交成功从队列移除，提交失败重新放回队列尾部
                    workflow_data = redis_client.lpop(email_title)
                    submit_result = archery_api.submit_sql_ticket(**json.loads(workflow_data))
                    if not submit_result['code']:
                        print(f"升级邮件： <{email_title}> ，SQL 工单： <{submit_result['workflow_name']}> 提交成功。响应消息：{submit_result['msg']}")
                    else:
                        print(f"升级邮件： <{email_title}> ，SQL 工单： <{submit_result['workflow_name']}> 提交失败。响应消息：{submit_result['msg']}")
                        redis_client.rpush(email_title, workflow_data)
                if not redis_client.llen(email_title):
                    redis_client.delete(email_title)
                    we_ins.sql_state = 2
                    we_ins.save()
        except AssertionError as err:
            we_ins.sql_state = 1
            we_ins.save()
            d_logger.error(err.__str__())
        except ObjectDoesNotExist:
            msg = f'当前升级邮件没有待执行 SQL 工单（sql_state=3），忽略本次任务'
            d_logger.info(msg)
        except Exception as err:
            msg = f'当前升级邮件待执行 SQL 工单： <{email_title}> 提交失败或异常，异常信息：{err.__str__()}'
            d_logger.info(msg)
    # 执行中 SQL 工单，调用 Archery 接口获取工单执行结果
    # in_progress = CICDState.objects.filter(flow_state=3, sql_state=2)
    # for i in range(len(in_progress)):
    #     try:
    #         ip_ins = in_progress.get(id=in_progress.values()[i]['id'])
    #         # TODO: 获取状态更新 sql_state，发送邮件
    #         print('执行中 SQL 工单....')
    #     except ObjectDoesNotExist:
    #         print('当前没有执行中 SQL 工单（sql_state=2），忽略本次任务')
    #     except Exception as err:
    #         print(f'执行中 SQL 工单获取状态失败或异常，异常信息：{err.__str__()}')

# 定时获取所有代码为待执行状态的工作流，提交到 CMDB 升级代码（过滤 SQL、config、Apollo 都已执行成功的工作流才执行此任务）
# @shared_task
# TODO: 定时任务升级代码功能
# def projectstate_task() -> None:
#     try:
#         cicdflow_state = CICDState.objects.filter(flow_state=3, project_state=3, sql_state=0, config_state=0, apollo_state=0)
#         print(cicdflow_state)
#         d_logger.info(cicdflow_state)
#     except CICDState.DoesNotExist:
#         d_logger.info('当前没有需执行代码升级邮件，忽略本次任务....')
#     except Exception as err:
#         print(f'task error: {err}')
#     return None
"""
Dear All：

１、升级开始时间：2023年01月30日 16:40
２、升级完成时间：2023年01月30日 17:06
３、升级人：SAD
４、以下内容已经升级完成：
 
UAT_A18_KRATOS_FRONTEND_V3
 
５、预计升级运营 12 ~ 20 分钟。
"""
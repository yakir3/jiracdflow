from django.db import models
# from django.utils.translation import gettext_lazy as _
from django.utils import timezone

def init_data():
    return {
        'sql_init_flag': 0,
        'nacos_init_flag': 0,
        'config_init_flag': 0,
        'code_init_flag': 0
    }

class JiraIssue(models.Model):
    issue_key = models.CharField(verbose_name='编号key值', primary_key=True, max_length=255)
    issue_id = models.CharField(verbose_name='编号ID', max_length=32)
    jira_project = models.CharField(verbose_name='Jira项目名称', max_length=16, default='UPGRADE')
    issue_type = models.CharField(verbose_name='事件类型', blank=False, null=False, max_length=16, default='升级')
    product_id = models.CharField(verbose_name='归属产品', blank=False, null=False, max_length=32)
    summary = models.CharField(verbose_name='概要标题', blank=False, null=False, unique=True, max_length=255)
    issue_status = models.CharField(verbose_name='事件当前状态', blank=False, null=False, max_length=64)
    environment = models.CharField(verbose_name='升级环境', blank=False, null=False, max_length=16)
    close_hall = models.CharField(verbose_name='升级是否需要维护', blank=False, null=False, max_length=8)
    function_list = models.TextField(verbose_name='功能列表', blank=False, null=False)

    sql_info = models.JSONField(verbose_name='SQL升级信息', blank=False, null=True)
    nacos_info = models.JSONField(verbose_name='Nacos升级信息', blank=False, null=True)
    config_info = models.JSONField(verbose_name='配置升级信息', blank=False, null=True)
    code_info = models.JSONField(verbose_name='代码升级信息', blank=False, null=True)
    # 初始化升级标志，0为首次升级，非0则为迭代升级
    init_flag = models.JSONField(verbose_name='初始化升级标志', blank=False, null=False, default=init_data)

    create_date = models.DateTimeField(default=timezone.now)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'jira_issue'
        ordering = ['-update_date']

    def __str__(self):
        return "Jira Issue Info: %s  %s" % (self.issue_key, self.summary)


class SqlWorkflow(models.Model):
    w_id = models.IntegerField(verbose_name='Archery工单ID', primary_key=True)
    sql_index = models.IntegerField(verbose_name='SQL文件升级序号', default=0)
    sql_release_info = models.CharField(verbose_name="SQL文件版本信息", max_length=64, default=0)
    # workflow_name = models.ForeignKey(
    #     'JiraWorkflow', verbose_name='工单名称',on_delete=models.CASCADE, to_field='summary', related_name='sql_workflow_name')
    workflow_name = models.CharField(verbose_name='工单名称', max_length=255)
    w_status = models.CharField(verbose_name='工单状态', max_length=64)

    create_date = models.DateTimeField(default=timezone.now)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sql_workflow'
        ordering = ['workflow_name', 'sql_index']

    def __str__(self):
        return str(self.sql_release_info)
from abc import ABC

from rest_framework import serializers
from .models import JiraWorkflow, SqlWorkflow

"""models 类序列化器"""
class CICDFlowSerializer(serializers.Serializer):
    project = serializers.CharField(max_length=16, allow_blank=True)
    summary = serializers.CharField(max_length=128)
    issue_type = serializers.CharField(max_length=16)
    env = serializers.CharField(max_length=16)
    function_list = serializers.JSONField()
    upgrade_type = serializers.CharField(max_length=32)
    sql_info = serializers.JSONField(allow_null=False)
    config_info = serializers.JSONField(allow_null=False)
    apollo_info = serializers.JSONField(allow_null=False)
    code_info = serializers.JSONField(allow_null=False)

class JiraWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = JiraWorkflow
        fields = '__all__'
        read_only_fields = ['create_date', 'init_flag']
        extra_kwargs = {
            'project': {'allow_blank': True}
        }

class SqlWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = SqlWorkflow
        fields = '__all__'
        # read_only_fields = ['workflow_name']
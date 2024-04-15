from abc import ABC

from rest_framework import serializers
from .models import JiraIssue, SqlWorkflow

"""models 类序列化器"""
class JiraIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = JiraIssue
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
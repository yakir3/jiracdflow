from rest_framework import serializers
from .models import CICDFlow, CICDState, JiraWorkflow

"""models 类序列化器"""
class CICDFlowSerializer(serializers.Serializer):
    project = serializers.CharField(max_length=16, allow_blank=True)
    summary = serializers.CharField(max_length=128)
    issue_type = serializers.CharField(max_length=16)
    env = serializers.CharField(max_length=16)
    function_list = serializers.JSONField()
    upgrade_type = serializers.CharField(max_length=32)
    sql_info = serializers.JSONField(allow_null=True)
    config_info = serializers.JSONField(allow_null=True)
    apollo_info = serializers.JSONField(allow_null=True)
    code_info = serializers.JSONField(allow_null=True)

class CICDStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CICDState
        fields = '__all__'
        read_only_fields = ['id', 'create_date']

class JiraWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = JiraWorkflow
        fields = '__all__'
        read_only_fields = ['create_date', 'init_flag']
        extra_kwargs = {
            'project': {'allow_blank': True}
        }
from django.urls import path, re_path
from .views import (
    JiraFlowView
)
from rest_framework.urlpatterns import format_suffix_patterns

app_name = 'cicdflow'

urlpatterns = [
    # cicdflow object
    # path('', CICDFlowView.as_view(), name='cicdflow_view'),
    re_path('^jira', JiraFlowView.as_view(), name='jiraflow_view'),
]

urlpatterns = format_suffix_patterns(urlpatterns)

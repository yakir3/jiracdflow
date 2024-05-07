from django.urls import path, re_path
from .views import (
    TestView,
    JiraFlowView
)
from rest_framework.urlpatterns import format_suffix_patterns

app_name = 'cicdflow'

urlpatterns = [
    # path('', CICDFlowView.as_view(), name='cicdflow_view'),
    path("test", TestView.as_view(), name="test"),
    re_path("^jira", JiraFlowView.as_view(), name="jiraflow_view"),
]

urlpatterns = format_suffix_patterns(urlpatterns)

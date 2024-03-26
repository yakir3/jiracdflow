"""
WSGI config for jiracdflow project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jiracdflow.settings')
project_env = os.environ.get('PROJECT_ENV', 'dev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jiracdflow.settings.{}'.format(project_env))

application = get_wsgi_application()

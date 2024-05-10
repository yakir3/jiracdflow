"""
ASGI config for jiracdflow project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

project_env = os.environ.get('PROJECT_ENV', 'dev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jiracdflow.settings.{}'.format(project_env))

application = get_asgi_application()

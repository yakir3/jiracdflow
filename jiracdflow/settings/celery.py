import os
from celery import Celery

project_env = os.environ.get('PROJECT_ENV', 'dev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jiracdflow.settings.{}'.format(project_env))

app = Celery('jiracdflow')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
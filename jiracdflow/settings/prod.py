from .base import *
# from datetime import timedelta
# from celery.schedules import crontab

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'jiracdflow',
        'USER': 'root',
        'PASSWORD': '1qaz@WSX',
        'HOST': '127.0.0.1',
        'PORT': 3307,
    }
}

TIME_ZONE = 'Asia/Shanghai'
USE_TZ = True
APPEND_SLASH = False

# # Celery Configuration Options
# # 时区设置
# CELERY_ENABLE_UTC = False
# CELERY_TIMEZONE = TIME_ZONE
# # 任务启动状态跟踪
# CELERY_TASK_TRACK_STARTED = True
# # 为任务设置超时时间，单位秒。超时即中止，执行下个任务
# CELERY_TASK_TIME_LIMIT = 30 * 60
# # 任务限流
# # CELERY_TASK_ANNOTATIONS = {'tasks.add': {'rate_limit': '10/s'}}
# # 为存储结果设置过期日期，默认1天过期。如果beat开启，Celery每天会自动清除。 设为0，存储结果永不过期
# CELERY_RESULT_EXPIRES = 7
# # Worker并发数量，一般默认CPU核数，可以不设置
# CELERY_WORKER_CONCURRENCY = 2
# # 每个worker执行了多少任务就会死掉，默认是无限的
# CELERY_WORKER_MAX_TASKS_PER_CHILD = 50
# # 定时任务配置
# CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
# CELERY_BEAT_SCHEDULE = {
#     "sqlstate-timed-task": {
#         "task": "cicdflow.tasks.sqlstate_task",
#         'schedule': timedelta(minutes=2),
#         # 'schedule': timedelta(seconds=10),
#         'args': ()
#     }
# }
# CELERY_BROKER_URL = "redis://localhost:6379/0"
# CELERY_RESULT_BACKEND = "redis://localhost:6379/1"

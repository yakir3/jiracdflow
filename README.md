[![Python](https://img.shields.io/badge/Python-3.10.9-red)](https://www.python.org/downloads/release/python-3109/)
[![Django](https://img.shields.io/badge/Django-4.1.3-blue)](https://docs.djangoproject.com/en/4.2/releases/4.1/)

## APP START 
```shell
# logs dir
mkdir logs 

# migrate db
python manage.py makemigrations
python manage.py migrate

# dev
python manage.py runserver 0.0.0.0:8888
# prod
uwsgi --ini uwsgi.ini
tail -f logs/uwsgi.log
```

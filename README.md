[![Python](https://img.shields.io/badge/Python-3.10.9-red)](https://www.python.org/downloads/release/python-3109/)
[![Django](https://img.shields.io/badge/Django-4.1.3-blue)](https://docs.djangoproject.com/en/4.2/releases/4.1/)

### Poetry Virtualenv Start
```shell
# Install
curl -sSL https://install.python-poetry.org | python -


# Create Virtualenv
#poetry env use /usr/bin/python3.10
poetry env use `which python3.10`


# Install denpencies
# poetry add Django==4.1.3
# poetry add xxxx
poetry install


# Project init
# Create logs dir
mkdir ./logs
# Init and migrate db
python manage.py makemigrations
python manage.py migrate
# Init config
mv config/config.yaml.default config/config.yaml


# Virtualenv start project
# Option 1
poetry shell
#python manage.py runserver 0.0.0.0:8080 # for dev
uwsgi --ini uwsgi.ini
# Option 2: for prod
#poetry run python manage.py runserver 0.0.0.0:8888 # for dev
poetry run uwsgi --ini uwsgi.ini
tail -f logs/uwsgi.log
```

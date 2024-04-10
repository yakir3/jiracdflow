[![Python](https://img.shields.io/badge/Python-3.10.9-red)](https://www.python.org/downloads/release/python-3109/)
[![Django](https://img.shields.io/badge/Django-4.1.3-blue)](https://docs.djangoproject.com/en/4.2/releases/4.1/)

### Docker start mysql
```shell
mkdir ./volume

docker run --name jiracdflow-mysql \
  -e MYSQL_ROOT_PASSWORD=123qwe \
  -e MYSQL_DATABASE=jiracdflow \
  -p 3307:3306 \
  -v $(pwd)/volume/mysql_data:/var/lib/mysql \
  -d mysql:5.7 --character-set-server=utf8mb4
```

### Poetry Virtualenv Init
```shell
# Install Python3.10
https://www.python.org/downloads/release/python-3109/


# Install Poetry
curl -sSL https://install.python-poetry.org | python -
export PATH="$PATH:/root/.local/bin"
#echo PATH="$PATH:/root/.local/bin" >> ~/.bashrc


# Create Virtualenv
#poetry env use /usr/local/python310/bin/python
poetry env use `which python3.10`


# Install denpencies
# poetry add Django==4.1.3
poetry install


# Project init
# Create dirs
mkdir ./logs ./static ./templates
# Init config
cp config/config.yaml.default config/config.yaml
```

### Virtualenv start project
```shell
# Option 1
# for dev
poetry shell
python manage.py makemigrations
python manage.py migrate
#python manage.py collectstatic --noinput
python manage.py runserver 0.0.0.0:8080

# for prod
export PROJECT_ENV=prod
poetry shell
python manage.py makemigrations
python manage.py migrate
#python manage.py collectstatic --noinput
uwsgi --ini uwsgi.ini


# Option 2
# for dev
poetry run python manage.py makemigrations
poetry run python manage.py migrate
#poetry run python manage.py collectstatic --noinput
poetry run python manage.py runserver 0.0.0.0:8888

# for prod
export PROJECT_ENV=prod
poetry run python manage.py makemigrations
poetry run python manage.py migrate
#poetry run python manage.py collectstatic --noinput
poetry run uwsgi --ini uwsgi.ini
#tail -f logs/uwsgi.log
```

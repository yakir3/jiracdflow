## APP START
```shell
# static dir
mkdir ./static
python manage.py collectstatic --noinput

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

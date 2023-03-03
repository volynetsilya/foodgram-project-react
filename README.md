http://84.201.140.94/

# Яндекс.Практикум: Продуктовый помощник Foodgram

### Описание.
На этом сервисе пользователи могут публиковать рецепты, подписываться на публикации других пользователей, добавлять понравившиеся рецепты в список «Избранное», а перед походом в магазин скачивать сводный список продуктов, необходимых для приготовления одного или нескольких выбранных блюд.

### Шаблон наполнения env-файла
###### env-файл (.env.example) находится в папке infra
DB_ENGINE=django.db.backends.postgresql\
DB_NAME= # название БД\ 
POSTGRES_USER= # ваше имя пользователя\
POSTGRES_PASSWORD= # пароль для доступа к БД\
DB_HOST=db\
DB_PORT=5432\

### Комнды для запуска приложения в контейнерах:
docker-compose up -d --build

###### Выполняем миграции:
docker-compose exec web python manage.py migrate

###### Создаем суперпользователя:
docker-compose exec web python manage.py createsuperuser

###### Србираем статику:
docker-compose exec web python manage.py collectstatic --no-input

###### Создаем дамп базы данных (нет в текущем репозитории):
docker-compose exec web python manage.py dumpdata > dumpPostrgeSQL.json

###### Останавливаем контейнеры:
docker-compose down -v

# Дополнительная информация.

### Технологии
Python 3.9D
Django 2.2
Postgresql

### Авторы
###### Илья Волынец

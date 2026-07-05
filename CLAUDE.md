# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Проект

WordCards — веб-сервис для изучения иностранных слов на Django 6 (Python 3.14, SQLite). Серверный рендеринг через Django templates + Bootstrap 5 по CDN; без REST API и JS-фреймворков. Интерфейс на русском языке.

## Команды

Виртуальное окружение — `venv/` в корне. В PowerShell:

```powershell
venv\Scripts\activate            # активировать окружение
python manage.py runserver       # запустить dev-сервер (http://127.0.0.1:8000/)
python manage.py makemigrations  # создать миграции
python manage.py migrate         # применить миграции
python manage.py test            # все тесты
python manage.py test accounts   # тесты одного приложения
python manage.py check           # проверка конфигурации
```

Без активации окружения можно вызывать напрямую: `venv\Scripts\python.exe manage.py ...`

## Архитектура

- Проект `wordcards/` (settings, корневой urls); приложения: `accounts/` — аутентификация и пользователи, `courses/` — курсы и карточки слов.
- **Кастомная модель пользователя** `accounts.models.User` (наследует `AbstractUser`), подключена через `AUTH_USER_MODEL = 'accounts.User'`. Ключевое поле — `role` (`TextChoices`): `creator` (создатель курсов) или `student` (ученик). Во всех ссылках на пользователя использовать `settings.AUTH_USER_MODEL` / `get_user_model()`, не `auth.User`.
- Аутентификация — встроенная: `LoginView`/`LogoutView` из `django.contrib.auth` плюс своя вьюха `signup` (форма `SignUpForm` на базе `UserCreationForm` с выбором роли и автовходом после регистрации). Маршруты — в `accounts/urls.py` под префиксом `/accounts/`.
- Шаблоны лежат в `accounts/templates/`: `base.html` (навбар с именем и ролью пользователя, кнопки входа/выхода), `home.html` (главная `/`), `registration/login.html` и `registration/signup.html`. Поля форм размечены вручную под Bootstrap-классы (`form-control`, `is-invalid`), а не через `{{ form }}` — при добавлении полей следовать этому стилю.
- Курсы: `Course` (автор — FK на пользователя, `seconds_per_word` для расчёта времени прохождения) и `Card` (слово/перевод, FK на курс, каскадное удаление). CRUD — классовые вьюхи в `courses/views.py`; права через миксины там же: `CreatorRequiredMixin` (создание — только роль creator) и `CourseAuthorRequiredMixin` (правка/удаление курса и карточек — только автор; переопределяет `get_course()`). Ученикам страница курса показывает карточки без переводов (`show_translations` в контексте). После добавления карточки редирект обратно на форму добавления. Расчёт времени — `Course.estimated_minutes`, в списке использует аннотацию `card_count` во избежание N+1.
- Флеш-сообщения (`django.contrib.messages`) выводятся в `base.html`.
- Выход из аккаунта — только POST-формой (требование Django 5+); ссылки `<a href>` на logout работать не будут.
- Тексты интерфейса и `verbose_name`/labels моделей и форм — на русском.

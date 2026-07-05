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
- Запись на курсы: `Enrollment` (ученик+курс с `UniqueConstraint`, статус active/completed/abandoned). Записываться могут только ученики (вьюха `enroll`, POST). Повторная запись после ухода не создаёт дубликат — та же запись переводится в active. «Покинуть курс» (кнопка на странице курса) ставит abandoned, запись не удаляется. Страница «Мои курсы» (`/courses/my/`) — только для роли student.
- Тренировка (`/courses/<pk>/train/`), система Лейтнера, двустороннее заучивание: единица — объект `CardProgress` (запись+карточка+направление, уникальны втроём; направления `word_to_translation` / `translation_to_word`, по два объекта на карточку — создаются при первом старте, для старых данных — data-миграцией 0006). В сессию отбирается до `SESSION_SIZE` (10) объектов — наименьший уровень, дольше не отвечавшиеся, уровень 5 исключается; направления независимы. Объект усвоен после `LEARNED_STREAK` (2) верных подряд; верный ответ без усвоения — в конец очереди, неверный — сброс счётчика и возврат через 2–3 позиции. Уровень (0–5) обновляется ТОЛЬКО в `_finish_session`: без ошибок +1, была ошибка — 0; в течение сессии пишется только `last_answered_at`. После обновления уровней там же проверяется завершение курса: все объекты записи (карточки × 2) на уровне 5 → статус completed и поздравительный экран в `train_summary.html`. Прогресс-бары курса (страница курса, «Мои курсы») — свойства Enrollment `learned_progress_count`/`total_progress_count` (знаменатель — карточки × 2). Состояние сессии — в `request.session['training_<enrollment_id>']` (с полем `v` — версия формата, старая отбрасывается); PRG-цикл `train` → `train_answer` (POST) → `train_feedback`. Вопрос/варианты строятся по направлению (`_question_for`, `_build_choices`: правильный ответ + до 3 переводов либо слов других карточек); варианты передаются скрытыми полями `choices` для подсветки на странице результата. После верного ответа — автопереход через 0.7 с с полоской-индикатором (инлайн-JS, без паузы по наведению, `<noscript>`-ссылка «Далее»); после неверного — только кнопка «Далее».
- Флеш-сообщения (`django.contrib.messages`) выводятся в `base.html`.
- Выход из аккаунта — только POST-формой (требование Django 5+); ссылки `<a href>` на logout работать не будут.
- Тексты интерфейса и `verbose_name`/labels моделей и форм — на русском.

import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from accounts.models import User

from .forms import CardForm, CourseForm
from .models import Card, CardProgress, Course, Enrollment


class CreatorRequiredMixin(UserPassesTestMixin):
    """Доступ только пользователям с ролью «создатель курсов»."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == User.Role.CREATOR


class CourseAuthorRequiredMixin(UserPassesTestMixin):
    """Доступ только автору курса (self.get_course() должен вернуть курс)."""

    def test_func(self):
        return self.request.user.is_authenticated and self.get_course().author_id == self.request.user.pk

    def get_course(self):
        return self.get_object()


class StudentRequiredMixin(UserPassesTestMixin):
    """Доступ только пользователям с ролью «ученик»."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == User.Role.STUDENT


class EnrollmentOwnerRequiredMixin(UserPassesTestMixin):
    """Доступ только ученику, которому принадлежит запись."""

    def test_func(self):
        return self.request.user.is_authenticated and self.get_object().student_id == self.request.user.pk


class CourseListView(LoginRequiredMixin, ListView):
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'

    def get_queryset(self):
        return (
            Course.objects
            .select_related('author')
            .annotate(card_count=Count('cards'))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role == User.Role.STUDENT:
            enrollment_by_course = {
                enrollment.course_id: enrollment
                for enrollment in Enrollment.objects.filter(student=self.request.user)
            }
            for course in context['courses']:
                course.enrollment = enrollment_by_course.get(course.pk)
        return context


class CourseDetailView(LoginRequiredMixin, DetailView):
    model = Course
    template_name = 'courses/course_detail.html'
    context_object_name = 'course'

    def get_queryset(self):
        return Course.objects.select_related('author').prefetch_related('cards')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_author'] = self.object.author_id == self.request.user.pk
        context['show_translations'] = self.request.user.role != User.Role.STUDENT
        if self.request.user.role == User.Role.STUDENT:
            context['enrollment'] = Enrollment.objects.filter(
                student=self.request.user, course=self.object,
            ).first()
        return context


class CourseCreateView(LoginRequiredMixin, CreatorRequiredMixin, CreateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/course_form.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, 'Курс создан.')
        return super().form_valid(form)


class CourseUpdateView(LoginRequiredMixin, CourseAuthorRequiredMixin, UpdateView):
    model = Course
    form_class = CourseForm
    template_name = 'courses/course_form.html'

    def form_valid(self, form):
        messages.success(self.request, 'Курс сохранён.')
        return super().form_valid(form)


class CourseDeleteView(LoginRequiredMixin, CourseAuthorRequiredMixin, DeleteView):
    model = Course
    template_name = 'courses/course_confirm_delete.html'
    context_object_name = 'course'
    success_url = reverse_lazy('course_list')

    def form_valid(self, form):
        messages.success(self.request, 'Курс удалён.')
        return super().form_valid(form)


@login_required
@require_POST
def enroll(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.user.role != User.Role.STUDENT:
        raise PermissionDenied('Записываться на курсы могут только ученики.')
    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user,
        course=course,
    )
    if created:
        messages.success(request, f'Вы записаны на курс «{course.title}».')
    elif enrollment.status == Enrollment.Status.ABANDONED:
        enrollment.status = Enrollment.Status.ACTIVE
        enrollment.save()
        messages.success(request, f'Вы снова записаны на курс «{course.title}».')
    else:
        messages.info(request, 'Вы уже записаны на этот курс.')
    return redirect('course_detail', pk=course.pk)


class MyCoursesView(LoginRequiredMixin, StudentRequiredMixin, ListView):
    template_name = 'courses/my_courses.html'
    context_object_name = 'enrollments'

    def get_queryset(self):
        return (
            Enrollment.objects
            .filter(student=self.request.user)
            .select_related('course', 'course__author')
            .annotate(card_count=Count('course__cards'))
        )


class EnrollmentLeaveView(LoginRequiredMixin, EnrollmentOwnerRequiredMixin, UpdateView):
    """Подтверждение и выход с курса: статус меняется на «прерван», запись не удаляется."""

    model = Enrollment
    fields = []
    template_name = 'courses/enrollment_confirm_leave.html'
    context_object_name = 'enrollment'

    def form_valid(self, form):
        form.instance.status = Enrollment.Status.ABANDONED
        messages.success(self.request, f'Вы покинули курс «{self.object.course.title}».')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('my_courses')


# --- Тренировка (система Лейтнера, двустороннее заучивание) ---
# Единица заучивания — объект CardProgress (карточка + направление).
# Сессия длится до завершения курса (или пока ученик не прервёт её):
# внутри неё порции по SESSION_SIZE объектов; когда порция усвоена,
# уровни обновляются (_finish_session), проверяется завершение курса,
# и если курс не завершён — без сводки подгружается следующая порция.
# Состояние сессии в request.session под ключом training_<enrollment_id>:
# {'v': 3, 'queue': [id объектов прогресса, первый — текущий вопрос],
#  'cards': {str(progress_id): {'streak': верных подряд, 'errors': ошибок}},
#  'learned': int, 'total': int — по текущей порции,
#  'learned_total': усвоено за всю сессию, 'correct': int, 'wrong': int,
#  'last': результат последнего ответа, 'done': bool, 'course_completed': bool}.
# Объект усвоен после LEARNED_STREAK верных подряд; уровень Лейтнера
# обновляется один раз по итогам порции (без ошибок +1, иначе 0).

SESSION_SIZE = 10
LEARNED_STREAK = 2
STATE_VERSION = 3


def _training_key(enrollment):
    return f'training_{enrollment.pk}'


def _get_training_enrollment(request, course):
    if not request.user.is_authenticated or request.user.role != User.Role.STUDENT:
        raise PermissionDenied('Тренировка доступна только ученикам.')
    # completed допускается, чтобы показать итоги сессии, завершившей курс
    enrollment = Enrollment.objects.filter(
        student=request.user, course=course,
        status__in=[Enrollment.Status.ACTIVE, Enrollment.Status.COMPLETED],
    ).first()
    if enrollment is None:
        raise PermissionDenied('Тренировка доступна только по активной записи на курс.')
    return enrollment


def _question_for(progress):
    """Возвращает (подсказка-вопрос, правильный ответ, поле для вариантов)."""
    card = progress.card
    if progress.direction == CardProgress.Direction.WORD_TO_TRANSLATION:
        return card.word, card.translation, 'translation'
    return card.translation, card.word, 'word'


def _build_choices(course, progress):
    prompt, answer, field = _question_for(progress)
    others = list(
        course.cards
        .exclude(pk=progress.card_id)
        .exclude(**{field: answer})
        .values_list(field, flat=True)
        .distinct()
    )
    choices = random.sample(others, min(3, len(others))) + [answer]
    random.shuffle(choices)
    return choices


def _start_session(course, enrollment):
    """Отбирает до SESSION_SIZE объектов прогресса (карточка + направление):
    наименьший уровень, дольше не показывались; уровень 5 не участвует."""
    card_ids = list(course.cards.values_list('id', flat=True))
    if not card_ids:
        return None
    existing = set(
        CardProgress.objects.filter(enrollment=enrollment).values_list('card_id', 'direction')
    )
    CardProgress.objects.bulk_create(
        CardProgress(enrollment=enrollment, card_id=card_id, direction=direction)
        for card_id in card_ids
        for direction in CardProgress.Direction.values
        if (card_id, direction) not in existing
    )
    selected = list(
        CardProgress.objects
        .filter(enrollment=enrollment, card__course=course, level__lt=CardProgress.MAX_LEVEL)
        .order_by('level', F('last_answered_at').asc(nulls_first=True))
        .values_list('id', flat=True)[:SESSION_SIZE]
    )
    if not selected:
        return None
    random.shuffle(selected)
    return {
        'v': STATE_VERSION,
        'queue': selected,
        'cards': {str(progress_id): {'streak': 0, 'errors': 0} for progress_id in selected},
        'learned': 0,
        'total': len(selected),
        'learned_total': 0,
        'correct': 0,
        'wrong': 0,
        'done': False,
        'course_completed': False,
    }


def _check_course_completed(enrollment):
    """Курс завершён, когда все объекты прогресса записи (карточки × 2)
    на уровне 5. Возвращает True, если статус переведён в completed."""
    total = enrollment.total_progress_count
    if (
        enrollment.status == Enrollment.Status.ACTIVE
        and total
        and enrollment.learned_progress_count >= total
    ):
        enrollment.status = Enrollment.Status.COMPLETED
        enrollment.save(update_fields=['status'])
        return True
    return False


def _finish_session(enrollment, state):
    """Итог сессии: усвоен без ошибок — уровень +1, была ошибка — уровень 0.
    Затем проверка завершения курса; возвращает True, если курс завершён."""
    for progress_id, info in state['cards'].items():
        progress = CardProgress.objects.filter(
            pk=int(progress_id), enrollment=enrollment,
        ).first()
        if progress is None:
            continue
        if info['errors']:
            progress.level = 0
        else:
            progress.level = min(progress.level + 1, CardProgress.MAX_LEVEL)
        progress.save(update_fields=['level'])

    return _check_course_completed(enrollment)


@login_required
def train(request, pk):
    course = get_object_or_404(Course, pk=pk)
    enrollment = _get_training_enrollment(request, course)
    key = _training_key(enrollment)
    state = request.session.get(key)
    if state is not None and state.get('v') != STATE_VERSION:
        state = None  # сессия из старой версии кода

    if state is None:
        state = _start_session(course, enrollment)
        if state is None:
            if course.cards.exists():
                # уровни могли достичь 5 вне обычного финала сессии — доводим статус
                if _check_course_completed(enrollment):
                    messages.success(request, f'Поздравляем! Курс «{course.title}» завершён.')
                else:
                    messages.success(request, 'Все карточки этого курса уже на максимальном уровне. Отличная работа!')
            else:
                messages.info(request, 'В этом курсе пока нет карточек для тренировки.')
            return redirect('course_detail', pk=course.pk)
        request.session[key] = state

    if state.get('done'):
        context = {
            'course': course,
            'correct': state['correct'],
            'wrong': state['wrong'],
            'total': state['learned_total'],
            'course_completed': state.get('course_completed', False),
        }
        del request.session[key]
        return render(request, 'courses/train_summary.html', context)

    progress = get_object_or_404(
        CardProgress.objects.select_related('card'),
        pk=state['queue'][0], enrollment=enrollment,
    )
    prompt, _answer, _field = _question_for(progress)
    return render(request, 'courses/train_question.html', {
        'course': course,
        'progress': progress,
        'prompt': prompt,
        'is_word_to_translation': progress.direction == CardProgress.Direction.WORD_TO_TRANSLATION,
        'choices': _build_choices(course, progress),
        'learned': state['learned'],
        'total': state['total'],
    })


@login_required
@require_POST
def train_answer(request, pk):
    course = get_object_or_404(Course, pk=pk)
    enrollment = _get_training_enrollment(request, course)
    key = _training_key(enrollment)
    state = request.session.get(key)
    if state is None or state.get('v') != STATE_VERSION or state.get('done'):
        return redirect('train', pk=course.pk)

    try:
        progress_id = int(request.POST.get('progress_id', 0))
    except ValueError:
        progress_id = 0
    # Устаревшая форма (повторная отправка, другая вкладка) — просто к текущему вопросу
    if progress_id != state['queue'][0]:
        return redirect('train', pk=course.pk)

    progress = get_object_or_404(
        CardProgress.objects.select_related('card'),
        pk=progress_id, enrollment=enrollment,
    )
    prompt, answer, _field = _question_for(progress)
    chosen = request.POST.get('choice', '')
    was_correct = chosen == answer

    progress.last_answered_at = timezone.now()
    progress.save(update_fields=['last_answered_at'])

    info = state['cards'][str(progress_id)]
    state['queue'].pop(0)
    if was_correct:
        state['correct'] += 1
        info['streak'] += 1
        if info['streak'] >= LEARNED_STREAK:
            state['learned'] += 1  # усвоен, в очередь не возвращается
        else:
            state['queue'].append(progress_id)
    else:
        state['wrong'] += 1
        info['streak'] = 0
        info['errors'] += 1
        # возврат через 2-3 позиции
        position = min(random.randint(2, 3), len(state['queue']))
        state['queue'].insert(position, progress_id)

    state['last'] = {
        'word': prompt,
        'chosen': chosen,
        'answer': answer,
        'was_correct': was_correct,
        # порядок вариантов с формы — чтобы показать их же с подсветкой
        'choices': request.POST.getlist('choices'),
        # снимок прогресса порции для страницы результата (до подгрузки следующей)
        'learned': state['learned'],
        'total': state['total'],
    }
    if not state['queue']:
        # порция усвоена: обновляем уровни и либо завершаем курс, либо продолжаем
        state['learned_total'] += state['learned']
        if _finish_session(enrollment, state):
            state['done'] = True
            state['course_completed'] = True
        else:
            next_batch = _start_session(course, enrollment)
            if next_batch is None:
                state['done'] = True  # подстраховка: тренировать больше нечего
            else:
                state['queue'] = next_batch['queue']
                state['cards'] = next_batch['cards']
                state['learned'] = 0
                state['total'] = next_batch['total']
    request.session[key] = state
    return redirect('train_feedback', pk=course.pk)


@login_required
def train_feedback(request, pk):
    course = get_object_or_404(Course, pk=pk)
    enrollment = _get_training_enrollment(request, course)
    state = request.session.get(_training_key(enrollment))
    if state is None or state.get('v') != STATE_VERSION or not state.get('last'):
        return redirect('train', pk=course.pk)
    last = state['last']
    return render(request, 'courses/train_feedback.html', {
        'course': course,
        'last': last,
        'learned': last.get('learned', state['learned']),
        'total': last.get('total', state['total']),
        'session_done': state.get('done', False),
    })


class CardCreateView(LoginRequiredMixin, CourseAuthorRequiredMixin, CreateView):
    model = Card
    form_class = CardForm
    template_name = 'courses/card_form.html'

    def get_course(self):
        return get_object_or_404(Course, pk=self.kwargs['course_pk'])

    def form_valid(self, form):
        form.instance.course = self.get_course()
        messages.success(self.request, f'Карточка «{form.instance.word}» добавлена.')
        return super().form_valid(form)

    def get_success_url(self):
        # Остаёмся на форме, чтобы сразу вводить следующую карточку
        return reverse('card_add', kwargs={'course_pk': self.kwargs['course_pk']})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course'] = self.get_course()
        return context


class CardUpdateView(LoginRequiredMixin, CourseAuthorRequiredMixin, UpdateView):
    model = Card
    form_class = CardForm
    template_name = 'courses/card_form.html'

    def get_course(self):
        return self.get_object().course

    def form_valid(self, form):
        messages.success(self.request, 'Карточка сохранена.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('course_detail', kwargs={'pk': self.object.course_id})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course'] = self.object.course
        return context


class CardDeleteView(LoginRequiredMixin, CourseAuthorRequiredMixin, DeleteView):
    model = Card
    template_name = 'courses/card_confirm_delete.html'
    context_object_name = 'card'

    def get_course(self):
        return self.get_object().course

    def form_valid(self, form):
        messages.success(self.request, 'Карточка удалена.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('course_detail', kwargs={'pk': self.object.course_id})

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Card, CardProgress, Course, Enrollment
from .views import _question_for

User = get_user_model()


class LeitnerAdvancementTests(TestCase):
    """Сложность заучивания: MAX_LEVEL=2, STREAK_TO_ADVANCE=1 — каждый верный
    ответ поднимает уровень на 1, направление выучивается за 2 верных ответа
    (в разных подходах); ошибка немедленно сбрасывает уровень в 0."""

    def setUp(self):
        self.student = User.objects.create_user(
            username='stud', password='pass12345', role=User.Role.STUDENT,
        )
        creator = User.objects.create_user(
            username='auth', password='pass12345', role=User.Role.CREATOR,
        )
        self.course = Course.objects.create(
            title='Test', description='', author=creator,
        )
        # одна карточка → два направления (два объекта CardProgress)
        Card.objects.create(course=self.course, word='dog', translation='собака')
        self.enrollment = Enrollment.objects.create(
            student=self.student, course=self.course,
            status=Enrollment.Status.ACTIVE,
        )
        self.client.force_login(self.student)
        self.train_url = reverse('train', kwargs={'pk': self.course.pk})
        self.answer_url = reverse('train_answer', kwargs={'pk': self.course.pk})
        # первый заход в тренировку строит очередь и объекты прогресса
        self.client.get(self.train_url)

    def _head(self):
        """id объекта прогресса в голове очереди (или None, если очередь пуста)."""
        state = self.client.session[f'training_{self.enrollment.pk}']
        if state.get('done') or not state.get('queue'):
            return None
        return state['queue'][0]

    def _answer(self, progress_id, correct):
        progress = CardProgress.objects.get(pk=progress_id)
        _prompt, answer, _field = _question_for(progress)
        choice = answer if correct else answer + '_wrong'
        self.client.post(self.answer_url, {
            'progress_id': progress_id,
            'choice': choice,
            'choices': [choice],
        })

    def test_constants(self):
        self.assertEqual(CardProgress.MAX_LEVEL, 2)
        self.assertEqual(CardProgress.STREAK_TO_ADVANCE, 1)

    def test_direction_learned_in_two_correct_answers(self):
        """Каждое направление доходит до MAX_LEVEL ровно за 2 верных ответа
        (0→1→2), а current_streak при этом не копится (всегда 0)."""
        answered = {}  # progress_id -> сколько раз ответили верно
        # прогресс-бар до первого ответа
        self.assertEqual(self.enrollment.level_progress_percent, 0)
        bar_before = 0

        for _ in range(50):  # с запасом; реально нужно 4 ответа (2 напр. × 2)
            head = self._head()
            if head is None:
                break
            self._answer(head, correct=True)
            answered[head] = answered.get(head, 0) + 1
            # промежуточная проверка уровня этого направления
            level = CardProgress.objects.get(pk=head).level
            self.assertEqual(level, answered[head])
            # стрик не копится — всегда 0 в БД
            self.assertEqual(
                CardProgress.objects.get(pk=head).current_streak, 0,
            )
            # полоска не откатывается на верном ответе
            self.enrollment.refresh_from_db()
            bar_now = self.enrollment.level_progress_percent
            self.assertGreaterEqual(bar_now, bar_before)
            bar_before = bar_now

        progresses = CardProgress.objects.filter(enrollment=self.enrollment)
        self.assertEqual(progresses.count(), 2)
        for progress in progresses:
            self.assertEqual(progress.level, CardProgress.MAX_LEVEL)
        # каждое направление выучено ровно за 2 верных ответа
        self.assertTrue(answered)
        self.assertTrue(all(count == 2 for count in answered.values()))
        # полоска дошла ровно до 100%
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.level_progress_percent, 100)

    def test_wrong_answer_resets_level_to_zero(self):
        """Ошибка сбрасывает level (и current_streak) направления в 0,
        даже если оно уже поднялось до уровня 1."""
        target = self._head()
        # поднимаем целевое направление до уровня 1
        self._answer(target, correct=True)
        self.assertEqual(CardProgress.objects.get(pk=target).level, 1)

        # доводим target снова до головы очереди, отвечая на остальные верно
        for _ in range(10):
            head = self._head()
            if head == target:
                break
            self._answer(head, correct=True)

        self.assertEqual(self._head(), target)
        self._answer(target, correct=False)

        reset = CardProgress.objects.get(pk=target)
        self.assertEqual(reset.level, 0)
        self.assertEqual(reset.current_streak, 0)

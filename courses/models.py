from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.urls import reverse


class Course(models.Model):
    title = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courses',
        verbose_name='Автор',
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Изменён', auto_now=True)

    class Meta:
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('course_detail', kwargs={'pk': self.pk})


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'В процессе'
        COMPLETED = 'completed', 'Завершён'
        ABANDONED = 'abandoned', 'Прерван'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='Ученик',
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='Курс',
    )
    status = models.CharField(
        'Статус',
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    enrolled_at = models.DateTimeField('Дата записи', auto_now_add=True)
    answers_correct = models.PositiveIntegerField('Верных ответов', default=0)
    answers_wrong = models.PositiveIntegerField('Неверных ответов', default=0)

    class Meta:
        verbose_name = 'Запись на курс'
        verbose_name_plural = 'Записи на курсы'
        constraints = [
            models.UniqueConstraint(fields=['student', 'course'], name='unique_student_course'),
        ]
        ordering = ['-enrolled_at']

    def __str__(self):
        return f'{self.student.username} — {self.course.title}'

    @property
    def total_progress_count(self):
        """Всего объектов прогресса: карточки × 2 направления."""
        return self.course.cards.count() * 2

    @property
    def learned_progress_count(self):
        return self.card_progresses.filter(level__gte=CardProgress.MAX_LEVEL).count()

    @property
    def learned_cards_count(self):
        """Полностью выученные карточки: оба направления на MAX_LEVEL."""
        return (
            self.card_progresses
            .filter(level__gte=CardProgress.MAX_LEVEL)
            .values('card')
            .annotate(directions=models.Count('id'))
            .filter(directions=len(CardProgress.Direction.values))
            .count()
        )

    @property
    def progress_percent(self):
        """Прогресс курса по карточкам: выучена, когда оба направления на максимуме."""
        total = self.course.cards.count()
        if not total:
            return 0
        return round(100 * self.learned_cards_count / total)

    @property
    def accuracy_percent(self):
        total = self.answers_correct + self.answers_wrong
        if not total:
            return 0
        return round(100 * self.answers_correct / total)


class CardProgress(models.Model):
    MAX_LEVEL = 2

    class Direction(models.TextChoices):
        WORD_TO_TRANSLATION = 'word_to_translation', 'Слово → перевод'
        TRANSLATION_TO_WORD = 'translation_to_word', 'Перевод → слово'

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='card_progresses',
        verbose_name='Запись',
    )
    card = models.ForeignKey(
        'Card',
        on_delete=models.CASCADE,
        related_name='progresses',
        verbose_name='Карточка',
    )
    direction = models.CharField(
        'Направление',
        max_length=20,
        choices=Direction.choices,
        default=Direction.WORD_TO_TRANSLATION,
    )
    level = models.PositiveSmallIntegerField(
        'Уровень',
        default=0,
        validators=[MaxValueValidator(MAX_LEVEL)],
    )
    last_answered_at = models.DateTimeField('Последний ответ', null=True, blank=True)

    class Meta:
        verbose_name = 'Прогресс по карточке'
        verbose_name_plural = 'Прогресс по карточкам'
        constraints = [
            models.UniqueConstraint(
                fields=['enrollment', 'card', 'direction'],
                name='unique_enrollment_card_direction',
            ),
        ]

    def __str__(self):
        return f'{self.enrollment} — {self.card.word} ({self.get_direction_display()}): {self.level}'


class Card(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='cards',
        verbose_name='Курс',
    )
    word = models.CharField('Слово', max_length=200)
    translation = models.CharField('Перевод', max_length=200)

    class Meta:
        verbose_name = 'Карточка'
        verbose_name_plural = 'Карточки'
        ordering = ['id']

    def __str__(self):
        return f'{self.word} — {self.translation}'

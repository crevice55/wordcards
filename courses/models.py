import math

from django.conf import settings
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
    seconds_per_word = models.PositiveIntegerField('Время на одно слово (сек)', default=30)
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

    @property
    def estimated_minutes(self):
        # Uses the annotated value when the queryset provides it, to avoid N+1 in lists
        count = getattr(self, 'card_count', None)
        if count is None:
            count = self.cards.count()
        return math.ceil(count * self.seconds_per_word / 60)


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
    seconds_per_word = models.PositiveIntegerField('Время на одно слово (сек)')
    status = models.CharField(
        'Статус',
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    enrolled_at = models.DateTimeField('Дата записи', auto_now_add=True)

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
    def estimated_minutes(self):
        count = getattr(self, 'card_count', None)
        if count is None:
            count = self.course.cards.count()
        return math.ceil(count * self.seconds_per_word / 60)


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

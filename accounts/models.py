from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CREATOR = 'creator', 'Создатель курсов'
        STUDENT = 'student', 'Ученик'

    role = models.CharField(
        'Роль',
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    def __str__(self):
        return self.username

from django.contrib.auth.forms import UserCreationForm

from .models import User


class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'role')
        labels = {
            'username': 'Имя пользователя',
            'role': 'Роль',
        }

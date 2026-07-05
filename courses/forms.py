from django import forms

from .models import Card, Course, Enrollment


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ('title', 'description', 'seconds_per_word')


class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ('word', 'translation')


class EnrollmentSettingsForm(forms.ModelForm):
    seconds_per_word = forms.IntegerField(
        label='Время на одно слово (секунд)',
        min_value=5,
        max_value=300,
        error_messages={
            'min_value': 'Минимальное время — 5 секунд.',
            'max_value': 'Максимальное время — 300 секунд.',
        },
    )

    class Meta:
        model = Enrollment
        fields = ('seconds_per_word',)

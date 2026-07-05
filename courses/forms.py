from django import forms

from .models import Card, Course


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ('title', 'description', 'seconds_per_word')


class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ('word', 'translation')

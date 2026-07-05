from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView, DeleteView, DetailView, ListView, UpdateView,
)

from accounts.models import User

from .forms import CardForm, CourseForm, EnrollmentSettingsForm
from .models import Card, Course, Enrollment


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
        defaults={'seconds_per_word': course.seconds_per_word},
    )
    if created:
        messages.success(request, f'Вы записаны на курс «{course.title}».')
    elif enrollment.status == Enrollment.Status.ABANDONED:
        enrollment.status = Enrollment.Status.ACTIVE
        enrollment.seconds_per_word = course.seconds_per_word
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


class EnrollmentSettingsView(LoginRequiredMixin, EnrollmentOwnerRequiredMixin, UpdateView):
    model = Enrollment
    form_class = EnrollmentSettingsForm
    template_name = 'courses/enrollment_settings.html'

    def form_valid(self, form):
        messages.success(self.request, 'Настройки сохранены.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('my_courses')


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

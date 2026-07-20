from django.contrib.auth import login
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from .forms import SignUpForm
from .models import User


class HomeView(TemplateView):
    template_name = 'home.html'

    def get_context_data(self, **kwargs):
        # Импорт внутри метода — модели курсов нужны только на главной,
        # это исключает лишнюю связанность модулей accounts ↔ courses.
        from courses.models import Course, Enrollment

        context = super().get_context_data(**kwargs)
        user = self.request.user
        if not user.is_authenticated:
            context['sample_courses'] = (
                Course.objects.select_related('author')
                .annotate(card_count=Count('cards'))[:6]
            )
        elif user.role == User.Role.CREATOR:
            context['creator_courses'] = (
                Course.objects.filter(author=user)
                .annotate(
                    card_count=Count('cards', distinct=True),
                    enrolled_count=Count('enrollments', distinct=True),
                    completed_count=Count(
                        'enrollments',
                        filter=Q(enrollments__ever_completed=True),
                        distinct=True,
                    ),
                )
            )
        else:  # student
            enrollments = list(
                Enrollment.objects.filter(student=user)
                .select_related('course')
                .annotate(
                    card_count=Count('course__cards', distinct=True),
                    progressed_count=Count(
                        'card_progresses',
                        filter=Q(card_progresses__level__gt=0),
                        distinct=True,
                    ),
                )
            )
            context['active_enrollments'] = [
                e for e in enrollments if e.status == Enrollment.Status.ACTIVE
            ]
            context['completed_enrollments'] = [
                e for e in enrollments if e.status == Enrollment.Status.COMPLETED
            ]
        return context


def signup(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})

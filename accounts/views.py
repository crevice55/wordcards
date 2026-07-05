from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from .forms import SignUpForm


class HomeView(TemplateView):
    template_name = 'home.html'


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

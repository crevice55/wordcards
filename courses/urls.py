from django.urls import path

from . import views

urlpatterns = [
    path('', views.CourseListView.as_view(), name='course_list'),
    path('create/', views.CourseCreateView.as_view(), name='course_create'),
    path('<int:pk>/', views.CourseDetailView.as_view(), name='course_detail'),
    path('<int:pk>/edit/', views.CourseUpdateView.as_view(), name='course_edit'),
    path('<int:pk>/delete/', views.CourseDeleteView.as_view(), name='course_delete'),
    path('<int:course_pk>/cards/add/', views.CardCreateView.as_view(), name='card_add'),
    path('cards/<int:pk>/edit/', views.CardUpdateView.as_view(), name='card_edit'),
    path('cards/<int:pk>/delete/', views.CardDeleteView.as_view(), name='card_delete'),
]

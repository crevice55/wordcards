from django.contrib import admin

from .models import Card, CardProgress, Course, Enrollment


class CardInline(admin.TabularInline):
    model = Card
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at', 'updated_at')
    list_filter = ('author',)
    search_fields = ('title', 'description')
    inlines = [CardInline]


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('word', 'translation', 'course')
    list_filter = ('course',)
    search_fields = ('word', 'translation')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'status', 'enrolled_at')
    list_filter = ('status', 'course')
    search_fields = ('student__username', 'course__title')


@admin.register(CardProgress)
class CardProgressAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'card', 'direction', 'level', 'last_answered_at')
    list_filter = ('level', 'direction', 'enrollment__course')
    search_fields = ('card__word', 'enrollment__student__username')

from django.contrib import admin

from .models import Card, Course


class CardInline(admin.TabularInline):
    model = Card
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'seconds_per_word', 'created_at', 'updated_at')
    list_filter = ('author',)
    search_fields = ('title', 'description')
    inlines = [CardInline]


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('word', 'translation', 'course')
    list_filter = ('course',)
    search_fields = ('word', 'translation')

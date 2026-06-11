from django.contrib import admin
from .models import Choice, Question

# Register your models here.

# 2. Create an Inline class for Choice
class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 3  # This provides 3 empty slots by default for new choices


# 3. Create a ModelAdmin for Question and attach the Inline
class QuestionAdmin(admin.ModelAdmin):
    
    fieldsets = [
        (None, {"fields": ["question_text"]}),
        ("Date information", {"fields": ["pub_date"], "classes": ["collapse"]}),
    ]
    list_display = ["question_text", "pub_date", "was_published_recently"]
    list_filter = ["pub_date"]
    search_fields = ["question_text"]
    inlines = [ChoiceInline]  # This hooks the choices into the question page


# 4. Register Question with its custom Admin class
admin.site.register(Question, QuestionAdmin)
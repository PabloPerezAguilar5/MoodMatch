from django.urls import path
from .views import mood_match

urlpatterns = [
    path('', mood_match, name='moodmatch'),
]

from django.urls import path

from . import views

app_name = 'weather'

urlpatterns = [
    path('', views.weather_index, name='index'),
    path('api/suggest/', views.city_suggestions_api, name='city_suggestions_api'),
]


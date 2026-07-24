from django.urls import path

from . import views

app_name = 'planner'

urlpatterns = [
    path('', views.calendar_view, name='calendar'),
    path('<int:year>/<int:month>/', views.calendar_view, name='calendar_month'),
    path('day/<int:year>/<int:month>/<int:day>/', views.day_detail, name='day_detail'),
    path('event/add/', views.event_create, name='event_create'),
    path('event/<int:pk>/edit/', views.event_update, name='event_update'),
    path('event/<int:pk>/delete/', views.event_delete, name='event_delete'),
]

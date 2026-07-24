from django.urls import path

from . import views

app_name = 'diary'

urlpatterns = [
    path('', views.diary_list, name='list'),
    path('new/', views.diary_create, name='create'),
    path('<int:pk>/', views.diary_detail, name='detail'),
    path('<int:pk>/edit/', views.diary_update, name='update'),
    path('<int:pk>/delete/', views.diary_delete, name='delete'),
]

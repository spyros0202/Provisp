from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('detail/<str:node_id>/', views.detail_view, name='detail'),
    path('autocomplete/', views.autocomplete_view, name='autocomplete'),
    path('chat/', views.chat_view, name='chat'),
    path('qa/', views.qa_redirect_view, name='qa_redirect'),
]

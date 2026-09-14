"""
W3Panel v2 — File Manager URLs
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.user_filemanager, name='user_filemanager'),
    path('<int:website_id>/', views.user_filemanager, name='user_filemanager_site'),
    path('api/', views.user_filemanager_api, name='user_filemanager_api'),
    path('<int:website_id>/api/', views.user_filemanager_api, name='user_filemanager_api_site'),
    path('upload/', views.user_filemanager_upload, name='user_filemanager_upload'),
    path('<int:website_id>/upload/', views.user_filemanager_upload, name='user_filemanager_upload_site'),
    path('download/', views.user_filemanager_download, name='user_filemanager_download'),
    path('<int:website_id>/download/', views.user_filemanager_download, name='user_filemanager_download_site'),
]
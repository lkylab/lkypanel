from django.urls import path
from . import views

urlpatterns = [
    path('site/<int:site_id>/',          views.index,    name='fm_index'),
    path('site/<int:site_id>/api/',      views.api,      name='fm_api'),
    path('site/<int:site_id>/upload/',   views.upload,   name='fm_upload'),
    path('site/<int:site_id>/download/', views.download, name='fm_download'),
]

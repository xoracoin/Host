from django.urls import path
from .views import (
    DatabaseListView, DatabaseSchemaView, DatabaseTableView,
    DatabaseSampleCreateView, DatabaseExportView
)

urlpatterns = [
    path('', DatabaseListView.as_view(), name='database_list'),
    path('sample/', DatabaseSampleCreateView.as_view(), name='database_sample'),
    path('<int:file_id>/schema/', DatabaseSchemaView.as_view(), name='database_schema'),
    path('<int:file_id>/table/<str:table_name>/', DatabaseTableView.as_view(), name='database_table'),
    path('<int:file_id>/export/', DatabaseExportView.as_view(), name='database_export'),
]

from django.urls import path
from . import views
from . import document_views

urlpatterns = [
    path(
        "documents/<uuid:document_id>/assess/",
        document_views.document_assess,
        name="document_assess",
    ),
    path(
        "documents/<uuid:document_id>/",
        document_views.document_detail,
        name="document_detail",
    ),
    path(
        "documents/<uuid:document_id>/analyze/",
        document_views.document_analyze,
        name="document_analyze",
    ),
    # This creates the endpoint at: /chat/
    path('chat/', views.chat_with_tutor, name='chat_with_tutor'),
    path('upload/', views.upload_document, name='upload_document'),
    path('documents/<uuid:document_id>/lesson/', views.generate_document_lesson_view, name='generate_document_lesson'),
    path('search/', views.search_resources, name='search_resources'),
    path('videos/', views.search_videos, name='search_videos'),
    path('active-learning/generate/', views.generate_active_learning, name='generate_active_learning'),
    path('active-learning/evaluate/', views.evaluate_theory_response, name='evaluate_theory_response'),
]
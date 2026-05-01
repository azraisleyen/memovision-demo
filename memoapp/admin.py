from django.contrib import admin
from .models import UploadedAnalysis


@admin.register(UploadedAnalysis)
class UploadedAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "status",
        "video_score",
        "brand_score",
        "duration_seconds",
        "created_at",
    )
    list_filter = ("status", "source_type", "created_at")
    search_fields = ("title", "source_url")
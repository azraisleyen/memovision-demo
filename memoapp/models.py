from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class UploadedAnalysis(models.Model):
    """
    Kullanıcının yüklediği veya linkten eklediği video için tüm analiz çıktıları
    bu model üzerinde tutulur.
    """

    STATUS_CHOICES = (
        ("processing", "İşleniyor"),
        ("completed", "Tamamlandı"),
        ("failed", "Başarısız"),
    )

    SOURCE_TYPE_CHOICES = (
        ("upload", "Dosya Yükleme"),
        ("url", "URL ile Ekleme"),
    )

    # Analizi oluşturan kullanıcı
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="analyses",
        null=True,
        blank=True,
    )

    # Analiz başlığı
    title = models.CharField(max_length=255)

    # Kaynak tipi: dosya mı URL mi
    source_type = models.CharField(max_length=20, default="upload")

    # Eğer URL ile geldiyse burada tutulur
    source_url = models.URLField(null=True, blank=True)

    # Sisteme kaydedilen video dosyası
    original_video = models.FileField(upload_to="videos/")

    # İlk kareden çıkarılan kapak resmi
    thumbnail = models.ImageField(upload_to="thumbnails/", null=True, blank=True)

    # Thumbnail üstünden üretilen heatmap
    heatmap = models.ImageField(upload_to="heatmaps/", null=True, blank=True)

    # Oluşturulan PDF rapor
    report_pdf = models.FileField(upload_to="reports/", null=True, blank=True)

    # Analiz skorları
    video_score = models.FloatField(default=0.0)
    brand_score = models.FloatField(default=0.0)
    video_confidence = models.FloatField(default=0.0)
    brand_confidence = models.FloatField(default=0.0)

    # Demo agent etkisi
    estimated_gain = models.FloatField(default=0.0)

    # Süre
    duration_seconds = models.FloatField(default=0.0)

    # Öne çıkan anlar / timeline verisi
    highlights_json = models.JSONField(default=list, blank=True)

    # Agent önerileri
    recommendations_json = models.JSONField(default=list, blank=True)

    # İşlem durumu
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="processing",
    )

    # Hata varsa burada tutulur
    error_message = models.TextField(null=True, blank=True)

    # Zaman damgaları
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.status}"

    @property
    def duration_display(self):
        """
        Süreyi mm:ss formatında döndürür.
        """
        total_seconds = int(self.duration_seconds or 0)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

class UserSubscription(models.Model):
    PLAN_CHOICES = (
        ("free", "Ücretsiz"),
        ("starter", "Başlangıç"),
        ("pro", "Profesyonel"),
        ("enterprise", "Kurumsal"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="subscription")
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="pro")
    plan_started_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.plan}"

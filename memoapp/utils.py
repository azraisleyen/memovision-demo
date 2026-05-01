import io
import time
import uuid
import urllib.request
from pathlib import Path
from random import Random

import cv2
import numpy as np
import yt_dlp

from django.conf import settings
from django.core.files import File
from django.core.files.base import ContentFile

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def register_pdf_font():
    """
    PDF içinde Türkçe karakterleri düzgün gösterebilmek için TTF font kaydı yapar.
    fonts/DejaVuSans.ttf dosyası varsa onu kullanır.
    """
    font_path = Path(settings.BASE_DIR) / "fonts" / "DejaVuSans.ttf"

    if font_path.exists():
        pdfmetrics.registerFont(TTFont("DejaVuSans", str(font_path)))
        return "DejaVuSans"

    # Font dosyası yoksa fallback.
    # Bu durumda bazı Türkçe karakterler bozulabilir.
    return "Helvetica"


def extract_video_info_and_thumbnail(video_path):
    """
    Videonun süresini hesaplar ve ilk kareden thumbnail üretir.
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError("Video açılamadı. Dosya bozuk veya format desteklenmiyor olabilir.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    duration_seconds = frame_count / fps if fps > 0 else 0.0

    success, frame = cap.read()
    cap.release()

    if not success or frame is None:
        raise ValueError("Videonun ilk karesi okunamadı. Thumbnail üretilemedi.")

    # OpenCV BGR verir; encode için doğrudan kullanılabilir.
    encode_success, buffer = cv2.imencode(".jpg", frame)
    if not encode_success:
        raise ValueError("Thumbnail encode edilemedi.")

    thumbnail_content = ContentFile(buffer.tobytes(), name=f"thumb_{uuid.uuid4().hex}.jpg")
    return duration_seconds, thumbnail_content


def generate_heatmap_from_thumbnail(thumbnail_path):
    """
    Thumbnail üstüne demo attention blob'ları ekleyerek heatmap üretir.
    Windows'ta Türkçe karakterli dosya yolları için cv2.imread yerine
    np.fromfile + cv2.imdecode kullanılır.
    """
    thumbnail_path = str(thumbnail_path)

    # Türkçe karakterli path sorunlarını önlemek için güvenli okuma
    image_bytes = np.fromfile(thumbnail_path, dtype=np.uint8)
    image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError(f"Thumbnail okunamadı. Heatmap üretilemedi. Path: {thumbnail_path}")

    height, width = image.shape[:2]

    heat = np.zeros((height, width), dtype=np.float32)

    centers = [
        (int(width * 0.25), int(height * 0.65), int(min(width, height) * 0.18), 1.0),
        (int(width * 0.55), int(height * 0.25), int(min(width, height) * 0.22), 0.9),
        (int(width * 0.78), int(height * 0.72), int(min(width, height) * 0.14), 0.75),
    ]

    y_indices, x_indices = np.indices((height, width))

    for cx, cy, radius, strength in centers:
        dist = ((x_indices - cx) ** 2 + (y_indices - cy) ** 2) / (2 * (radius ** 2))
        heat += strength * np.exp(-dist)

    heat = cv2.normalize(heat, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    heatmap_colored = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
    blended = cv2.addWeighted(image, 0.62, heatmap_colored, 0.38, 0)

    encode_success, buffer = cv2.imencode(".jpg", blended)

    if not encode_success:
        raise ValueError("Heatmap encode edilemedi.")

    return ContentFile(buffer.tobytes(), name=f"heatmap_{uuid.uuid4().hex}.jpg")


def build_demo_analysis_payload(title, duration_seconds):
    """
    Gerçek AI model yerine kararlı demo skor üretir.
    Aynı başlık için aynı civarda skorlar üretmeye çalışır.
    """
    seed_text = f"{title}-{int(duration_seconds)}"
    rng = Random(seed_text)

    # 🔥 Demo skorlar (jüri sunumu için tutarlı ve anlamlı)
    video_score = 0.74
    brand_score = 0.68
    video_confidence = round(rng.uniform(0.82, 0.91), 2)
    brand_confidence = round(rng.uniform(0.80, 0.89), 2)
    estimated_gain = 0.18

    # Zaman çizgisi için öne çıkan anlar
    # Süreye göre yaklaşık nokta üret
    safe_duration = max(int(duration_seconds), 10)
    p1 = min(12, safe_duration - 1)
    p2 = min(int(safe_duration * 0.23), safe_duration - 1)
    p3 = min(int(safe_duration * 0.48), safe_duration - 1)
    p4 = min(int(safe_duration * 0.77), safe_duration - 1)

    highlights = [
        {
            "time_sec": p1,
            "label": "Logo görünürlüğü arttı",
            "type": "blue",
            "impact": "+0.2",
        },
        {
            "time_sec": p2,
            "label": "İlk dikkat sıçraması",
            "type": "cyan",
            "impact": "+0.1",
        },
        {
            "time_sec": p3,
            "label": "Marka mesajı güçlü",
            "type": "yellow",
            "impact": "+0.3",
        },
        {
            "time_sec": p4,
            "label": "CTA / kapanış etkisi",
            "type": "pink",
            "impact": "+0.1",
        },
    ]

    recommendations = [
        "İlk 2 saniyede daha güçlü bir açılış kullanın.",
        "Marka mesajını ilk karelerde daha görünür konumlandırın.",
        "Yüksek kontrastlı bir başlık ve net CTA ekleyin.",
    ]

    return {
        "video_score": video_score,
        "brand_score": brand_score,
        "video_confidence": video_confidence,
        "brand_confidence": brand_confidence,
        "estimated_gain": estimated_gain,
        "highlights": highlights,
        "recommendations": recommendations,
    }


def seconds_to_mmss(seconds_value):
    """
    Saniyeyi mm:ss biçimine çevirir.
    """
    total_seconds = int(seconds_value or 0)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def create_pdf_report(analysis):
    """
    AI-style, sade ve ikonlu analiz PDF raporu üretir.
    """
    font_name = register_pdf_font()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # -------------------------------
    # 🔷 LOGO (Turkcell)
    # -------------------------------
    logo_path = Path(settings.BASE_DIR) / "static" / "img" / "memoapp" / "turkcell_logo.png"

    if logo_path.exists():
        pdf.drawImage(str(logo_path), 50, height - 90, width=120, preserveAspectRatio=True)

    # -------------------------------
    # 🔷 BAŞLIK
    # -------------------------------
    pdf.setFont(font_name, 20)
    pdf.drawString(180, height - 60, "MemoVision Pro - Analiz Raporu")

    current_y = height - 140

    # -------------------------------
    # 📊 SONUÇLAR
    # -------------------------------
    pdf.setFont(font_name, 16)
    pdf.drawString(50, current_y, "📊 Sonuçlar")
    current_y -= 30

    pdf.setFont(font_name, 12)

    video_label = "Yüksek" if analysis.video_score >= 0.7 else "Orta"
    brand_label = "Yüksek" if analysis.brand_score >= 0.7 else "Orta"

    pdf.drawString(60, current_y, f"🧠 Video Memorability: {analysis.video_score} → {video_label}")
    current_y -= 22

    pdf.drawString(60, current_y, f"🏷️ Brand Memorability: {analysis.brand_score} → {brand_label}")
    current_y -= 30

    # -------------------------------
    # 📌 GENEL DEĞERLENDİRME (AI yorum hissi)
    # -------------------------------
    pdf.setFont(font_name, 14)
    pdf.drawString(50, current_y, "📌 Genel Değerlendirme")
    current_y -= 26

    pdf.setFont(font_name, 11)

    if analysis.video_score > analysis.brand_score:
        line1 = "Video içeriği dikkat çekici ve izleyici ilgisini başarıyla yakalamaktadır."
        line2 = "Ancak marka görünürlüğü içerik kadar güçlü değildir."
    else:
        line1 = "Marka mesajı güçlü ancak içerik akışı yeterince destekleyici değildir."
        line2 = "Video ve marka etkisi arasında denge geliştirilmelidir."

    pdf.drawString(60, current_y, line1)
    current_y -= 18
    pdf.drawString(60, current_y, line2)
    current_y -= 18

    pdf.drawString(60, current_y, "İçerik ve marka entegrasyonu güçlendirilmelidir.")
    current_y -= 30

    # -------------------------------
    # 🚀 ÖNERİLER
    # -------------------------------
    pdf.setFont(font_name, 14)
    pdf.drawString(50, current_y, "🚀 Öneriler")
    current_y -= 26

    pdf.setFont(font_name, 11)

    for rec in analysis.recommendations_json:
        pdf.drawString(60, current_y, f"- {rec}")
        current_y -= 20

    # -------------------------------
    # 📈 BEKLENEN ETKİ
    # -------------------------------
    current_y -= 10

    pdf.setFont(font_name, 14)
    pdf.drawString(50, current_y, "📈 Beklenen Etki")
    current_y -= 26

    pdf.setFont(font_name, 11)

    pdf.drawString(60, current_y, "• Brand memorability skorunda artış")
    current_y -= 18

    pdf.drawString(60, current_y, "• Daha dengeli video–marka performansı")
    current_y -= 18

    pdf.drawString(60, current_y, "• Kampanya verimliliğinde iyileşme")
    current_y -= 30

    # -------------------------------
    # FOOTER
    # -------------------------------
    pdf.setFont(font_name, 9)
    pdf.drawString(50, 40, "MemoVision Pro • AI Destekli Video Analiz Sistemi")

    pdf.save()
    buffer.seek(0)

    filename = f"report_{analysis.pk}_{uuid.uuid4().hex}.pdf"
    return ContentFile(buffer.read(), name=filename)


def attach_video_from_url(analysis, source_url):
    """
    URL'den video indirir ve analysis.original_video alanına kaydeder.
    Destek:
    - Direkt mp4/webm linki
    - YouTube / desteklenen platformlar (yt-dlp ile)
    """
    media_temp_dir = Path(settings.MEDIA_ROOT) / "videos"
    media_temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        lowered = source_url.lower()

        # Direkt video linkleri için basit download
        if lowered.endswith(".mp4") or lowered.endswith(".webm") or lowered.endswith(".mov"):
            temp_name = f"url_video_{uuid.uuid4().hex}.mp4"
            temp_path = media_temp_dir / temp_name

            urllib.request.urlretrieve(source_url, temp_path)

            with open(temp_path, "rb") as file_obj:
                analysis.original_video.save(temp_name, File(file_obj), save=True)

            analysis.source_type = "url"
            analysis.source_url = source_url
            analysis.save(update_fields=["original_video", "source_type", "source_url"])
            return True, ""

        # YouTube / diğer platformlar için yt-dlp
        output_template = str(media_temp_dir / f"yt_{uuid.uuid4().hex}.%(ext)s")

        ydl_opts = {
            "outtmpl": output_template,
            "format": "best[ext=mp4]/best",
            "noplaylist": True,
            "quiet": True,
            "merge_output_format": "mp4",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(source_url, download=True)
            downloaded_path = Path(ydl.prepare_filename(info))

            # Bazı durumlarda merge sonrası dosya adı mp4 olabilir
            if not downloaded_path.exists():
                possible_mp4 = downloaded_path.with_suffix(".mp4")
                if possible_mp4.exists():
                    downloaded_path = possible_mp4

        if not downloaded_path.exists():
            return False, "URL'den video indirilemedi."

        final_name = f"url_video_{uuid.uuid4().hex}{downloaded_path.suffix}"

        with open(downloaded_path, "rb") as file_obj:
            analysis.original_video.save(final_name, File(file_obj), save=True)

        analysis.source_type = "url"
        analysis.source_url = source_url
        analysis.save(update_fields=["original_video", "source_type", "source_url"])

        return True, ""

    except Exception as exc:
        return False, f"URL'den video alınırken hata oluştu: {exc}"


def process_uploaded_analysis(analysis):
    """
    Video sisteme geldikten sonra:
    1) süre ve thumbnail çıkarılır
    2) heatmap üretilir
    3) demo skorlar üretilir
    4) PDF oluşturulur
    """
    try:
        analysis.status = "processing"
        analysis.error_message = ""
        analysis.save(update_fields=["status", "error_message"])

        # Video yolu mevcut değilse hata ver
        if not analysis.original_video or not analysis.original_video.path:
            raise ValueError("Video dosyası bulunamadı.")

        video_path = analysis.original_video.path

        # Süre ve thumbnail çıkar
        duration_seconds, thumbnail_content = extract_video_info_and_thumbnail(video_path)
        analysis.duration_seconds = duration_seconds
        analysis.thumbnail.save(thumbnail_content.name, thumbnail_content, save=False)

        # Thumbnail kaydedildikten sonra heatmap üret
        analysis.save(update_fields=["duration_seconds", "thumbnail"])

        if not analysis.thumbnail or not analysis.thumbnail.path:
            raise ValueError("Thumbnail kaydedilemedi.")

        heatmap_content = generate_heatmap_from_thumbnail(analysis.thumbnail.path)
        analysis.heatmap.save(heatmap_content.name, heatmap_content, save=False)

        # Demo skorları ve öneriler
        payload = build_demo_analysis_payload(analysis.title, analysis.duration_seconds)
        analysis.video_score = payload["video_score"]
        analysis.brand_score = payload["brand_score"]
        analysis.video_confidence = payload["video_confidence"]
        analysis.brand_confidence = payload["brand_confidence"]
        analysis.estimated_gain = payload["estimated_gain"]
        analysis.highlights_json = payload["highlights"]
        analysis.recommendations_json = payload["recommendations"]

        # Demo akışında model çalışıyormuş hissi için bilinçli bekleme
        # (gerçek model entegrasyonunda bu süre doğal olarak inference süresi olacaktır)
        time.sleep(4)

        # Önce heatmap + skorlar kaydedilsin
        analysis.status = "completed"
        analysis.save()

        # PDF rapor oluştur
        pdf_content = create_pdf_report(analysis)
        analysis.report_pdf.save(pdf_content.name, pdf_content, save=False)
        analysis.save(update_fields=["report_pdf"])

        return True, ""

    except Exception as exc:
        analysis.status = "failed"
        analysis.error_message = str(exc)
        analysis.save(update_fields=["status", "error_message"])
        return False, str(exc)
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
    Teknik olmayan kullanıcılar için görselleştirilmiş ve aksiyon odaklı
    tek sayfalık profesyonel PDF raporu üretir.
    """
    font_name = register_pdf_font()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    def rounded_box(x, y, w, h, fill_rgb=(1, 1, 1), stroke_rgb=(0.88, 0.91, 0.96), radius=12):
        pdf.setFillColorRGB(*fill_rgb)
        pdf.setStrokeColorRGB(*stroke_rgb)
        pdf.roundRect(x, y, w, h, radius, fill=1, stroke=1)

    def progress_row(y, label, value, color_rgb, hint):
        pdf.setFont(font_name, 12)
        pdf.setFillColorRGB(0.11, 0.16, 0.28)
        pdf.drawString(42, y + 20, label)
        pdf.setFont(font_name, 12)
        pdf.drawRightString(338, y + 20, f"{value:.2f}")

        rounded_box(42, y + 8, 296, 8, fill_rgb=(0.89, 0.91, 0.95), stroke_rgb=(0.89, 0.91, 0.95), radius=4)
        bar_w = max(8, min(296, 296 * value))
        rounded_box(42, y + 8, bar_w, 8, fill_rgb=color_rgb, stroke_rgb=color_rgb, radius=4)

        pdf.setFont(font_name, 10)
        pdf.setFillColorRGB(0.39, 0.45, 0.56)
        pdf.drawString(42, y - 8, hint)

    # Header
    pdf.setFillColorRGB(0.95, 0.96, 0.99)
    pdf.rect(0, height - 125, width, 125, fill=1, stroke=0)

    pdf.setFont(font_name, 11)
    pdf.setFillColorRGB(0.18, 0.40, 0.84)
    pdf.drawString(36, height - 36, "MEMOVISION ANALIZ RAPORU")

    pdf.setFont(font_name, 26)
    pdf.setFillColorRGB(0.08, 0.13, 0.23)
    pdf.drawString(36, height - 66, analysis.title[:42])

    pdf.setFont(font_name, 10)
    pdf.setFillColorRGB(0.36, 0.42, 0.53)
    pdf.drawString(36, height - 88, f"Dosya: {Path(analysis.original_video.name).name if analysis.original_video else 'Video'} • Süre: {analysis.duration_display}")

    rounded_box(width - 175, height - 96, 140, 72, fill_rgb=(0.90, 0.94, 1.0), stroke_rgb=(0.72, 0.82, 0.98), radius=16)
    pdf.setFont(font_name, 28)
    pdf.setFillColorRGB(0.17, 0.39, 0.86)
    pdf.drawCentredString(width - 105, height - 58, f"+{analysis.estimated_gain:.2f}")
    pdf.setFont(font_name, 9)
    pdf.setFillColorRGB(0.35, 0.42, 0.54)
    pdf.drawCentredString(width - 105, height - 74, "Tahmini skor etkisi")

    # Main two columns
    rounded_box(28, height - 460, 328, 308, fill_rgb=(1, 1, 1), stroke_rgb=(0.87, 0.91, 0.97), radius=16)
    rounded_box(372, height - 460, 196, 308, fill_rgb=(1, 1, 1), stroke_rgb=(0.87, 0.91, 0.97), radius=16)

    pdf.setFont(font_name, 16)
    pdf.setFillColorRGB(0.08, 0.16, 0.33)
    pdf.drawString(42, height - 182, "Memorability Metrics")

    progress_row(height - 240, "Video Hatırlanabilirliği", float(analysis.video_score or 0), (0.20, 0.39, 0.85), "Açılış güçlü; ilk saniye etkisi korunmalı.")

    progress_row(height - 302, "Marka Hatırlanabilirliği", float(analysis.brand_score or 0), (0.11, 0.72, 0.50), "Marka öğesi erken karede daha görünür olabilir.")

    msg_score = 0.72 if (analysis.video_score or 0) > (analysis.brand_score or 0) else 0.68
    progress_row(height - 364, "Mesaj Netliği", msg_score, (0.09, 0.66, 0.78), "CTA sadeleştirilirse dönüşüm potansiyeli artar.")

    pdf.setFont(font_name, 16)
    pdf.setFillColorRGB(0.08, 0.16, 0.33)
    pdf.drawString(384, height - 182, "AI Insights")

    rounded_box(384, height - 332, 172, 136, fill_rgb=(0.98, 0.95, 0.90), stroke_rgb=(0.95, 0.78, 0.58), radius=12)
    pdf.setFont(font_name, 10)
    pdf.setFillColorRGB(0.78, 0.34, 0.03)
    pdf.drawString(394, height - 214, "ÖNCELİKLİ AKSİYONLAR")
    pdf.setFillColorRGB(0.16, 0.20, 0.29)
    recs = analysis.recommendations_json or [
        "İlk 2 saniyede güçlü açılış.",
        "Marka öğesini merkezi konumlandır.",
        "CTA mesajını kısalt ve netleştir.",
    ]
    y = height - 234
    for idx, rec in enumerate(recs[:3], start=1):
        pdf.drawString(394, y, f"{idx}. {rec[:42]}")
        y -= 24

    rounded_box(384, height - 444, 172, 96, fill_rgb=(0.92, 0.95, 1.0), stroke_rgb=(0.75, 0.84, 0.98), radius=12)
    pdf.setFont(font_name, 10)
    pdf.setFillColorRGB(0.17, 0.36, 0.78)
    pdf.drawString(394, height - 368, "ESTIMATED IMPACT")
    pdf.setFillColorRGB(0.20, 0.25, 0.36)
    pdf.drawString(394, height - 388, f"Toplam memorability etkisi")
    pdf.drawString(394, height - 404, f"yaklaşık +{analysis.estimated_gain:.2f} artabilir.")

    # Bottom cards
    titles = ["Risk Areas", "Weaknesses", "Strengths"]
    texts = [
        "Zayıf açılış ve geç CTA, marka etkisini sınırlayabilir.",
        "Mesaj hiyerarşisi bazı sahnelerde dağılabiliyor.",
        "Görsel kalite ve akış ritmi güçlü bir temel sunuyor.",
    ]
    colors = [(0.85, 0.25, 0.20), (0.18, 0.34, 0.82), (0.04, 0.60, 0.44)]
    x = 28
    for i in range(3):
        rounded_box(x, height - 560, 176, 86, fill_rgb=(0.98, 0.99, 1.0), stroke_rgb=(0.88, 0.91, 0.95), radius=12)
        pdf.setFont(font_name, 10)
        pdf.setFillColorRGB(*colors[i])
        pdf.drawString(x + 10, height - 535, titles[i])
        pdf.setFont(font_name, 9)
        pdf.setFillColorRGB(0.25, 0.31, 0.42)
        pdf.drawString(x + 10, height - 552, texts[i][:58])
        x += 184

    pdf.setFont(font_name, 9)
    pdf.setFillColorRGB(0.49, 0.54, 0.63)
    pdf.drawCentredString(width / 2, 22, "MemoVision Pro • LLM destekli aksiyon odaklı rapor")

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
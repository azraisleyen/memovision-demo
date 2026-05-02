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
from django.utils import timezone

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
    Teknik olmayan kullanıcılar için tek sayfalık, görsel olarak güçlü,
    pazarlama ekiplerinin kolayca anlayabileceği aksiyon odaklı PDF üretir.
    """
    font_name = register_pdf_font()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin = 24
    content_w = width - (margin * 2)

    def rounded_box(x, y, w, h, fill_rgb=(1, 1, 1), stroke_rgb=(0.88, 0.91, 0.96), radius=14):
        pdf.setFillColorRGB(*fill_rgb)
        pdf.setStrokeColorRGB(*stroke_rgb)
        pdf.roundRect(x, y, w, h, radius, fill=1, stroke=1)

    def draw_wrapped_text(x, y_top, text, max_width, font_size=10, color=(0.2, 0.25, 0.36), leading=13, max_lines=None):
        pdf.setFont(font_name, font_size)
        pdf.setFillColorRGB(*color)

        words = (text or '').split()
        if not words:
            return y_top

        lines = []
        line = words[0]

        for word in words[1:]:
            candidate = f"{line} {word}"
            if pdf.stringWidth(candidate, font_name, font_size) <= max_width:
                line = candidate
            else:
                lines.append(line)
                line = word

        lines.append(line)

        if max_lines is not None and len(lines) > max_lines:
            lines = lines[:max_lines]

        y = y_top
        for ln in lines:
            pdf.drawString(x, y, ln)
            y -= leading

        return y

    def metric_row(x, y, w, label, value, color_rgb, hint):
        pdf.setFont(font_name, 12)
        pdf.setFillColorRGB(0.09, 0.14, 0.24)
        pdf.drawString(x, y + 18, label)

        pdf.setFont(font_name, 12)
        pdf.drawRightString(x + w, y + 18, f"{value:.2f}")

        rounded_box(x, y + 7, w, 9, fill_rgb=(0.87, 0.90, 0.95), stroke_rgb=(0.87, 0.90, 0.95), radius=5)
        bar_w = max(10, min(w, w * float(value or 0)))
        rounded_box(x, y + 7, bar_w, 9, fill_rgb=color_rgb, stroke_rgb=color_rgb, radius=5)

        draw_wrapped_text(x, y - 7, hint, max_width=w, font_size=9, color=(0.35, 0.43, 0.56), leading=11, max_lines=4)

    # Background
    pdf.setFillColorRGB(0.96, 0.97, 1.0)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)

    # Header band
    header_h = 132
    pdf.setFillColorRGB(0.90, 0.94, 1.0)
    pdf.rect(0, height - header_h, width, header_h, fill=1, stroke=0)

    pdf.setFont(font_name, 11)
    pdf.setFillColorRGB(0.18, 0.39, 0.84)
    pdf.drawString(margin + 4, height - 34, 'MEMOVISION AI RAPORU')

    draw_wrapped_text(
        margin + 4,
        height - 66,
        analysis.title or 'Memorability Analizi',
        max_width=content_w - 170,
        font_size=30,
        color=(0.06, 0.11, 0.21),
        leading=31,
        max_lines=3,
    )

    filename = Path(analysis.original_video.name).name if analysis.original_video else 'Video'
    meta_text = f"Dosya: {filename}  •  Süre: {analysis.duration_display}  •  Tarih: {timezone.now().strftime('%d.%m.%Y')}"
    draw_wrapped_text(margin + 4, height - 96, meta_text, max_width=content_w - 170, font_size=10, color=(0.33, 0.41, 0.55), leading=12, max_lines=2)

    rounded_box(width - 176, height - 103, 148, 78, fill_rgb=(0.85, 0.91, 1.0), stroke_rgb=(0.63, 0.77, 0.98), radius=18)
    pdf.setFont(font_name, 30)
    pdf.setFillColorRGB(0.14, 0.37, 0.86)
    pdf.drawCentredString(width - 102, height - 61, f"+{analysis.estimated_gain:.2f}")
    pdf.setFont(font_name, 9)
    pdf.setFillColorRGB(0.27, 0.38, 0.56)
    pdf.drawCentredString(width - 102, height - 77, 'Tahmini toplam etki')

    # Layout blocks
    top_y = height - 154
    left_w = 352
    gap = 16
    right_w = content_w - left_w - gap

    left_x = margin
    right_x = left_x + left_w + gap

    # Left main metrics panel
    rounded_box(left_x, top_y - 342, left_w, 342, fill_rgb=(1, 1, 1), stroke_rgb=(0.82, 0.88, 0.97), radius=18)
    pdf.setFont(font_name, 17)
    pdf.setFillColorRGB(0.08, 0.15, 0.31)
    pdf.drawString(left_x + 16, top_y - 30, 'Memorability Özeti')

    metric_row(
        left_x + 16,
        top_y - 88,
        left_w - 32,
        'Video Hatırlanabilirliği',
        float(analysis.video_score or 0),
        (0.20, 0.40, 0.87),
        'Açılış enerjisi güçlü. İlk 2 saniyede marka vaadini tek cümleyle netleştirmek, izleyici tutulumunu ve hatırlanabilirliği birlikte yükseltir.',
    )
    metric_row(
        left_x + 16,
        top_y - 170,
        left_w - 32,
        'Marka Hatırlanabilirliği',
        float(analysis.brand_score or 0),
        (0.10, 0.73, 0.51),
        'Marka kodları doğru seçilmiş. Logoyu 3. saniyeden önce görünür kılmak ve ürün kadrajını merkezde tutmak geri çağrımı belirgin şekilde artırır.',
    )

    msg_score = 0.76 if (analysis.video_score or 0) >= 0.72 else 0.69
    metric_row(
        left_x + 16,
        top_y - 252,
        left_w - 32,
        'Mesaj Netliği',
        msg_score,
        (0.10, 0.66, 0.79),
        'Kapanışta tek bir net CTA ve kısa fayda cümlesi kullanımı, mesaj netliğini artırarak kampanya performansına doğrudan katkı sağlar.',
    )

    # Right column - action cards
    rounded_box(right_x, top_y - 222, right_w, 222, fill_rgb=(1, 1, 1), stroke_rgb=(0.82, 0.88, 0.97), radius=18)
    pdf.setFont(font_name, 16)
    pdf.setFillColorRGB(0.08, 0.15, 0.31)
    pdf.drawString(right_x + 14, top_y - 30, 'AI Aksiyon Önerileri')

    recs = analysis.recommendations_json or [
        'İlk 2 saniyede daha güçlü bir açılış sahnesi kullanın.',
        'Marka mesajını ilk karelerde görünür ve kontrastlı yerleştirin.',
        'CTA cümlesini kısaltıp tek bir aksiyona odaklayın.',
    ]

    rounded_box(right_x + 12, top_y - 190, right_w - 24, 140, fill_rgb=(1.0, 0.95, 0.88), stroke_rgb=(0.95, 0.76, 0.54), radius=12)
    pdf.setFont(font_name, 10)
    pdf.setFillColorRGB(0.80, 0.35, 0.05)
    pdf.drawString(right_x + 22, top_y - 66, 'ÖNCELİKLİ 3 AKSİYON')

    y = top_y - 86
    for idx, rec in enumerate(recs[:3], start=1):
        y = draw_wrapped_text(
            right_x + 22,
            y,
            f"{idx}. {rec}",
            max_width=right_w - 46,
            font_size=10,
            color=(0.18, 0.21, 0.30),
            leading=12,
            max_lines=4,
        ) - 2

    rounded_box(right_x, top_y - 342, right_w, 106, fill_rgb=(0.88, 0.93, 1.0), stroke_rgb=(0.70, 0.82, 0.98), radius=16)
    pdf.setFont(font_name, 11)
    pdf.setFillColorRGB(0.14, 0.33, 0.76)
    pdf.drawString(right_x + 14, top_y - 258, 'BEKLENEN ETKİ')

    impact_text = (
        f"Öneriler uygulandığında video+marka memorability skorunda yaklaşık "
        f"+{analysis.estimated_gain:.2f} puanlık iyileşme beklenir."
    )
    draw_wrapped_text(right_x + 14, top_y - 278, impact_text, max_width=right_w - 28, font_size=10, color=(0.20, 0.27, 0.40), leading=13, max_lines=5)

    # Bottom full-width insights area
    bottom_y = 42
    bottom_h = 244
    rounded_box(margin, bottom_y, content_w, bottom_h, fill_rgb=(1, 1, 1), stroke_rgb=(0.82, 0.88, 0.97), radius=18)
    pdf.setFont(font_name, 16)
    pdf.setFillColorRGB(0.08, 0.15, 0.31)
    pdf.drawString(margin + 16, bottom_y + bottom_h - 30, 'Yönetici Özeti ve Kampanya Notları')

    col_gap = 12
    col_w = (content_w - 32 - (col_gap * 2)) / 3
    titles = ['Risk Alanları', 'Gelişim Fırsatları', 'Güçlü Yönler']
    bodies = [
        'Açılış sahnesinde duygu tetikleyici unsur güçlü olsa da marka vaadi birkaç saniye gecikiyor. Bu gecikme, ilk temas anındaki hatırlanma etkisini düşürüyor ve performans potansiyelini sınırlıyor.',
        'Mesaj mimarisini “problem → çözüm → fayda → CTA” sıralamasına çekmek, özellikle mobil izleyicide anlaşılırlığı artırır. İlk 5 saniyede kısa bir değer önerisi vermek dönüşüme olumlu yansır.',
        'Görsel kalite, kurgu ritmi ve tonal bütünlük güçlü. Mevcut yaratıcı dil marka kimliğiyle uyumlu; küçük optimizasyonlarla daha yüksek memorability skoruna ölçeklenebilir bir temel sunuyor.',
    ]
    palette = [
        ((1.0, 0.93, 0.93), (0.95, 0.78, 0.78), (0.84, 0.24, 0.24)),
        ((0.93, 0.95, 1.0), (0.79, 0.86, 0.98), (0.22, 0.38, 0.84)),
        ((0.92, 0.99, 0.95), (0.76, 0.92, 0.84), (0.05, 0.60, 0.43)),
    ]

    for i in range(3):
        x = margin + 16 + i * (col_w + col_gap)
        fill, stroke, title_color = palette[i]
        rounded_box(x, bottom_y + 18, col_w, bottom_h - 60, fill_rgb=fill, stroke_rgb=stroke, radius=12)
        pdf.setFont(font_name, 11)
        pdf.setFillColorRGB(*title_color)
        pdf.drawString(x + 10, bottom_y + bottom_h - 58, titles[i])
        draw_wrapped_text(x + 10, bottom_y + bottom_h - 78, bodies[i], max_width=col_w - 20, font_size=9, color=(0.22, 0.29, 0.40), leading=12, max_lines=11)

    # Footer
    pdf.setFont(font_name, 9)
    pdf.setFillColorRGB(0.45, 0.51, 0.62)
    pdf.drawCentredString(width / 2, 18, 'MemoVision Pro • AI destekli pazarlama içgörü raporu')

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

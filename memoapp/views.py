import os

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from .forms import AnalysisCreateForm, LoginForm, RegisterForm, UserSettingsForm
from .models import UploadedAnalysis
from .utils import attach_video_from_url, process_uploaded_analysis


def landing(request):
    """
    Public landing sayfası.
    Giriş yapan kullanıcı tekrar landing'de kalmaz, yeni analiz ekranına gider.
    """
    if request.user.is_authenticated:
        return redirect("new_analysis")

    return render(request, "memoapp/landing.html")


def public_plans(request):
    """
    Giriş yapmadan görülebilen planlar sayfası.
    """
    plans = [
        {
            "name": "Ücretsiz",
            "price": "₺0",
            "description": "Ürünü denemek isteyen kullanıcılar için 2 ücretsiz analiz hakkı.",
            "features": ["2 ücretsiz analiz", "Video skoru", "Marka skoru", "Temel AI raporu"],
            "highlight": False,
        },
        {
            "name": "Başlangıç",
            "price": "$99 / ay",
            "description": "Küçük kampanyalar ve bireysel pazarlama ekipleri için temel analiz paketi.",
            "features": ["Günlük 3 analiz", "Video + marka skoru", "Dashboard görünümü", "Kısa öneri raporu"],
            "highlight": False,
        },
        {
            "name": "Profesyonel",
            "price": "$219 / ay",
            "description": "Ekipler için gelişmiş analiz, heatmap ve öneri akışı.",
            "features": ["Günlük 25 analiz", "Heatmap önizleme", "Gelişmiş AI önerileri", "Ekip kullanımı"],
            "highlight": True,
        },
        {
            "name": "Kurumsal",
            "price": "Pay as you go",
            "description": "API, özel entegrasyon ve kuruma özel kullanım ihtiyaçları için.",
            "features": ["API erişimi", "Özel entegrasyon", "Kurumsal destek", "Özelleştirilebilir kullanım"],
            "highlight": False,
        },
    ]

    return render(request, "memoapp/public_plans.html", {"plans": plans})


class CustomLoginView(LoginView):
    """
    Kullanıcı giriş sayfası.
    GET: login.html gösterir.
    POST: giriş başarılıysa yeni analiz sayfasına yönlendirir.
    """
    template_name = "memoapp/login.html"
    authentication_form = LoginForm
    success_url = reverse_lazy("new_analysis")
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.success_url

    def form_invalid(self, form):
        messages.error(self.request, "Giriş başarısız. Bilgilerinizi kontrol edin.")
        return super().form_invalid(form)

    def form_valid(self, form):
        messages.success(self.request, "Giriş başarılı.")
        return super().form_valid(form)


def register_view(request):
    """
    Kullanıcı kayıt sayfası.
    GET: register.html gösterir.
    POST: kayıt başarılıysa kullanıcıyı otomatik giriş yaptırıp yeni analiz sayfasına gönderir.
    """
    if request.user.is_authenticated:
        return redirect("new_analysis")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.first_name = form.cleaned_data["first_name"]
            user.email = form.cleaned_data["email"]
            user.save()

            login(request, user)
            messages.success(request, "Kayıt başarılı. Hoş geldiniz.")
            return redirect("new_analysis")

        messages.error(request, "Kayıt formunda hata var. Lütfen bilgileri kontrol edin.")

    else:
        form = RegisterForm()

    return render(request, "memoapp/register.html", {"form": form})


def logout_view(request):
    """
    Kullanıcı çıkış işlemi.
    """
    logout(request)
    messages.info(request, "Çıkış yapıldı.")
    return redirect("landing")


def build_dashboard_suggestions(analysis):
    """
    Dashboard için zaman bazlı öneriler üretir.
    """
    video_score = float(analysis.video_score or 0)
    brand_score = float(analysis.brand_score or 0)

    suggestions = []

    if video_score < 0.70:
        suggestions.append({
            "time": "0:00–0:02",
            "seek": 0,
            "title": "Problem: Açılış etkisini güçlendir",
            "impact": "+0.08",
            "text": "Insight: İlk 2 saniyede dikkat düşüyor. Öneri: Güçlü hook sahnesi. Beklenen etki: izlenme tutunması artar.",
        })
    else:
        suggestions.append({
            "time": "0:00–0:02",
            "seek": 0,
            "title": "Insight: Güçlü açılışı koru",
            "impact": "+0.04",
            "text": "Açılış performansı güçlü. Aynı tempo korunursa hatırlanabilirlik korunur.",
        })

    if brand_score < 0.70:
        suggestions.append({
            "time": "0:03–0:08",
            "seek": 3,
            "title": "Problem: Marka görünürlüğünü artır",
            "impact": "+0.06",
            "text": "Insight: Marka öğeleri geç ve düşük kontrastta kalıyor. Öneri: Logo/ürün merkezi ve yüksek kontrast. Etki: marka hatırlanması yükselir.",
        })
    else:
        suggestions.append({
            "time": "0:03–0:08",
            "seek": 3,
            "title": "Insight: Marka temasını sürdür",
            "impact": "+0.04",
            "text": "Marka görünürlüğü yeterli. Öneri: aynı görsel dilin devamı ile tutarlılık korunmalı.",
        })

    suggestions.append({
        "time": "0:12–0:18",
        "seek": 12,
        "title": "Öneri: CTA ve mesaj hiyerarşisini netleştir",
        "impact": "+0.06",
        "text": "Kapanış mesajı kısa, okunabilir ve aksiyon odaklı olmalıdır.",
    })

    return suggestions


@login_required
def new_analysis(request):
    """
    Yeni analiz oluşturma ekranı.
    """
    if request.method == "POST":
        form = AnalysisCreateForm(request.POST, request.FILES)

        if form.is_valid():
            analysis = form.save(commit=False)
            analysis.user = request.user
            analysis.status = "processing"
            analysis.save()

            uploaded_file = form.cleaned_data.get("original_video")
            source_url = form.cleaned_data.get("source_url")

            if not uploaded_file and source_url:
                ok, error = attach_video_from_url(analysis, source_url)

                if not ok:
                    analysis.status = "failed"
                    analysis.error_message = error
                    analysis.save(update_fields=["status", "error_message"])
                    messages.error(request, error)
                    return redirect("new_analysis")

            ok, error = process_uploaded_analysis(analysis)

            if ok:
                messages.success(request, "Video başarıyla analiz edildi.")
                return redirect("dashboard", analysis_id=analysis.pk)

            analysis.status = "failed"
            analysis.error_message = error
            analysis.save(update_fields=["status", "error_message"])

            messages.error(request, error)
            return redirect("new_analysis")

        messages.error(request, "Form geçerli değil. Lütfen tekrar deneyin.")

    else:
        form = AnalysisCreateForm()

    recent_analyses = UploadedAnalysis.objects.filter(
        user=request.user
    ).order_by("-created_at")[:3]

    return render(request, "memoapp/new_analysis.html", {
        "form": form,
        "recent_analyses": recent_analyses,
    })


@login_required
def dashboard(request, analysis_id):
    """
    Analiz sonuç dashboard'u.
    """
    analysis = get_object_or_404(
        UploadedAnalysis,
        pk=analysis_id,
        user=request.user,
    )

    analyses = UploadedAnalysis.objects.filter(
        user=request.user
    ).order_by("-created_at")

    suggestions = build_dashboard_suggestions(analysis)

    return render(request, "memoapp/dashboard.html", {
        "analysis": analysis,
        "analyses": analyses,
        "suggestions": suggestions,
    })


@login_required
def projects(request):
    """
    Geçmiş analizler.
    """
    analyses = UploadedAnalysis.objects.filter(
        user=request.user
    ).order_by("-created_at")

    return render(request, "memoapp/projects.html", {"analyses": analyses})


@login_required
def settings_view(request):
    """
    Kullanıcı ayarları.
    """
    if request.method == "POST":
        form = UserSettingsForm(request.POST, instance=request.user)

        if form.is_valid():
            form.save()
            messages.success(request, "Ayarlar kaydedildi.")
            return redirect("settings_page")

    else:
        form = UserSettingsForm(instance=request.user)

    total_analyses = UploadedAnalysis.objects.filter(user=request.user).count()
    remaining = max(100 - total_analyses, 0)

    return render(request, "memoapp/settings.html", {
        "form": form,
        "total_analyses": total_analyses,
        "remaining": remaining,
    })


@login_required
def download_report(request, pk):
    """
    PDF rapor indirir.
    """
    analysis = get_object_or_404(
        UploadedAnalysis,
        pk=pk,
        user=request.user,
    )

    if not analysis.report_pdf:
        raise Http404("Rapor bulunamadı.")

    report_path = analysis.report_pdf.path

    if not os.path.exists(report_path):
        raise Http404("Rapor dosyası fiziksel olarak mevcut değil.")

    return FileResponse(
        open(report_path, "rb"),
        as_attachment=True,
        filename=f"memovision_report_{analysis.pk}.pdf",
    )


@login_required
def report_view(request, pk):
    """
    HTML rapor sayfası.
    """
    analysis = get_object_or_404(
        UploadedAnalysis,
        pk=pk,
        user=request.user,
    )

    video_score = float(analysis.video_score or 0)
    brand_score = float(analysis.brand_score or 0)

    video_label = "Yüksek" if video_score >= 0.70 else "Orta"
    brand_label = "Yüksek" if brand_score >= 0.70 else "Orta"

    if video_score > brand_score:
        main_comment = (
            "Video içeriği izleyici ilgisini desteklemektedir. Buna karşın marka "
            "unsurlarının daha erken ve görünür konumlandırılması önerilir."
        )
        summary = "İçerik etkisi güçlüdür; marka görünürlüğü artırılmalıdır."
    elif brand_score > video_score:
        main_comment = (
            "Marka görünürlüğü belirli seviyede sağlanmıştır. Video akışı, açılış etkisi "
            "ve mesaj netliği güçlendirilirse kampanya etkisi artabilir."
        )
        summary = "Marka varlığı güçlüdür; video etkisi geliştirilebilir."
    else:
        main_comment = (
            "Video ve marka skorları dengelidir. Küçük optimizasyonlarla daha güçlü "
            "bir sonuç alınabilir."
        )
        summary = "Video ve marka etkisi dengelidir."

    suggestions = build_dashboard_suggestions(analysis)

    return render(request, "memoapp/report.html", {
        "analysis": analysis,
        "video_label": video_label,
        "brand_label": brand_label,
        "main_comment": main_comment,
        "summary": summary,
        "suggestions": suggestions,
    })
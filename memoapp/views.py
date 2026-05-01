import os

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from .forms import AnalysisCreateForm, LoginForm, RegisterForm, UserSettingsForm
from .models import UploadedAnalysis, UserSubscription
from .plans import PLAN_CONFIG, get_plan_config
from .utils import attach_video_from_url, process_uploaded_analysis


def _get_or_create_subscription(user):
    sub, _ = UserSubscription.objects.get_or_create(user=user)
    return sub


def _build_plan_context(user):
    sub = _get_or_create_subscription(user)
    plan = get_plan_config(sub.plan)
    total_analyses = UploadedAnalysis.objects.filter(
        user=user,
        status="completed",
        created_at__date=timezone.localdate(),
    ).count()

    limit = plan["limit"]
    if limit is None:
        remaining_text = "Sınırsız"
        progress_pct = 0
    else:
        remaining_text = f"{max(limit - total_analyses, 0)} / {limit}"
        progress_pct = min(int((total_analyses / limit) * 100), 100)

    return {
        "current_plan": plan,
        "current_plan_key": sub.plan,
        "total_analyses": total_analyses,
        "remaining_text": remaining_text,
        "progress_pct": progress_pct,
    }


def landing(request):
    if request.user.is_authenticated:
        return redirect("new_analysis")
    return render(request, "memoapp/landing.html")


def public_plans(request):
    plans = [
        {
            "key": "free",
            "name": "Ücretsiz",
            "price": "₺0",
            "description": "2 analiz hakkı. Sadece video memorability.",
            "features": ["2 analiz hakkı", "Video memorability", "Temel AI raporu"],
            "highlight": False,
        },
        {
            "key": "starter",
            "name": "Başlangıç",
            "price": "$99 / ay",
            "description": "Günlük 3 analiz. Sadece video memorability.",
            "features": ["Günlük 3 analiz", "Video memorability", "Dashboard"],
            "highlight": False,
        },
        {
            "key": "pro",
            "name": "Profesyonel",
            "price": "$219 / ay",
            "description": "Günlük 25 analiz. Video + marka memorability.",
            "features": ["Günlük 25 analiz", "Video + marka memorability", "Gelişmiş AI önerileri"],
            "highlight": True,
        },
        {
            "key": "enterprise",
            "name": "Kurumsal",
            "price": "Pay as you go",
            "description": "Sınırsız analiz. Video + marka memorability.",
            "features": ["Sınırsız analiz", "Video + marka memorability", "API / özel entegrasyon"],
            "highlight": False,
        },
    ]
    return render(request, "memoapp/public_plans.html", {"plans": plans})


class CustomLoginView(LoginView):
    template_name = "memoapp/login.html"
    authentication_form = LoginForm
    success_url = reverse_lazy("new_analysis")
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.success_url


def register_view(request):
    if request.user.is_authenticated:
        return redirect("new_analysis")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.first_name = form.cleaned_data["first_name"]
            user.email = form.cleaned_data["email"]
            user.save()
            UserSubscription.objects.get_or_create(user=user, defaults={"plan": "free"})
            login(request, user)
            messages.success(request, "Kayıt başarılı. Hoş geldiniz.")
            return redirect("new_analysis")
        messages.error(request, "Kayıt formunda hata var. Lütfen bilgileri kontrol edin.")
    else:
        form = RegisterForm()

    return render(request, "memoapp/register.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.info(request, "Çıkış yapıldı.")
    return redirect("landing")


def build_dashboard_suggestions(analysis):
    return [{"time": "0:00–0:02", "seek": 0, "title": "Öneri", "impact": "+0.05", "text": "Açılış hook’unu güçlendirin."}]


@login_required
def new_analysis(request):
    plan_ctx = _build_plan_context(request.user)
    current_plan = plan_ctx["current_plan"]

    if request.method == "POST":
        if current_plan["limit"] is not None and plan_ctx["total_analyses"] >= current_plan["limit"]:
            messages.error(request, f"{current_plan['name']} planı analiz limitine ulaştınız.")
            return redirect("settings_page")

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
                if not current_plan["brand_enabled"]:
                    analysis.brand_score = 0.0
                    analysis.brand_confidence = 0.0
                    analysis.save(update_fields=["brand_score", "brand_confidence"])
                messages.success(request, "Video başarıyla analiz edildi.")
                return redirect("dashboard", analysis_id=analysis.pk)

            messages.error(request, error)
            return redirect("new_analysis")

        messages.error(request, "Form geçerli değil. Lütfen tekrar deneyin.")
    else:
        form = AnalysisCreateForm()

    recent_analyses = UploadedAnalysis.objects.filter(user=request.user).order_by("-created_at")[:3]
    return render(request, "memoapp/new_analysis.html", {"form": form, "recent_analyses": recent_analyses, **plan_ctx})


@login_required
def dashboard(request, analysis_id):
    analysis = get_object_or_404(UploadedAnalysis, pk=analysis_id, user=request.user)
    analyses = UploadedAnalysis.objects.filter(user=request.user).order_by("-created_at")
    suggestions = build_dashboard_suggestions(analysis)
    return render(request, "memoapp/dashboard.html", {"analysis": analysis, "analyses": analyses, "suggestions": suggestions, **_build_plan_context(request.user)})


@login_required
def projects(request):
    analyses = UploadedAnalysis.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "memoapp/projects.html", {"analyses": analyses, **_build_plan_context(request.user)})


@login_required
def settings_view(request):
    subscription = _get_or_create_subscription(request.user)
    if request.method == "POST":
        form = UserSettingsForm(request.POST, instance=request.user)
        selected_plan = request.POST.get("plan")
        if form.is_valid():
            form.save()
            if selected_plan in PLAN_CONFIG:
                if subscription.plan != selected_plan:
                    subscription.plan = selected_plan
                    subscription.save(update_fields=["plan"])
            messages.success(request, "Ayarlar kaydedildi.")
            return redirect("settings_page")
    else:
        form = UserSettingsForm(instance=request.user)

    plan_ctx = _build_plan_context(request.user)
    return render(request, "memoapp/settings.html", {
        "form": form,
        "plans": PLAN_CONFIG.values(),
        "selected_plan": subscription.plan,
        **plan_ctx,
    })


@login_required
def download_report(request, pk):
    analysis = get_object_or_404(UploadedAnalysis, pk=pk, user=request.user)
    if not analysis.report_pdf:
        raise Http404("Rapor bulunamadı.")
    report_path = analysis.report_pdf.path
    if not os.path.exists(report_path):
        raise Http404("Rapor dosyası fiziksel olarak mevcut değil.")
    return FileResponse(open(report_path, "rb"), as_attachment=True, filename=f"memovision_report_{analysis.pk}.pdf")


@login_required
def report_view(request, pk):
    analysis = get_object_or_404(UploadedAnalysis, pk=pk, user=request.user)
    return render(request, "memoapp/report.html", {"analysis": analysis, "video_label": "Yüksek" if analysis.video_score >= 0.7 else "Orta", "brand_label": "Yüksek" if analysis.brand_score >= 0.7 else "Orta", "main_comment": "Genel değerlendirme", "summary": "Özet", "suggestions": build_dashboard_suggestions(analysis), **_build_plan_context(request.user)})

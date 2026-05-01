from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import UploadedAnalysis


class LoginForm(AuthenticationForm):
    """
    Landing sayfasındaki giriş formu.
    """
    username = forms.CharField(
        label="Kullanıcı Adı",
        widget=forms.TextInput(attrs={"class": "input-field", "placeholder": "Kullanıcı adınız"})
    )
    password = forms.CharField(
        label="Şifre",
        widget=forms.PasswordInput(attrs={"class": "input-field", "placeholder": "Şifreniz"})
    )


class RegisterForm(UserCreationForm):
    """
    Landing sayfasındaki kayıt formu.
    """
    first_name = forms.CharField(
        label="Ad Soyad",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "input-field", "placeholder": "Adınız Soyadınız"})
    )
    email = forms.EmailField(
        label="E-posta",
        widget=forms.EmailInput(attrs={"class": "input-field", "placeholder": "siz@example.com"})
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "email", "password1", "password2"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "input-field", "placeholder": "Kullanıcı adı"}),
        }


class AnalysisCreateForm(forms.ModelForm):
    """
    Yeni analiz formu.
    Hem video upload hem URL destekler.
    """

    source_url = forms.URLField(
        required=False,
        label="URL'den ekle",
        widget=forms.URLInput(
            attrs={
                "class": "input-field",
                "placeholder": "YouTube, Vimeo veya direkt .mp4 linki yapıştır",
                "id": "id_source_url",
            }
        ),
    )

    class Meta:
        model = UploadedAnalysis
        fields = ["title", "original_video", "source_url"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "input-field",
                    "placeholder": "Analiz başlığı",
                }
            ),
            "original_video": forms.ClearableFileInput(
                attrs={
                    "class": "hidden-file-input",
                    "accept": "video/mp4,video/quicktime,video/webm,video/*",
                }
            ),
        }

    def clean(self):
        """
        Kullanıcı ya dosya yüklemeli ya da URL girmeli.
        """
        cleaned_data = super().clean()
        original_video = cleaned_data.get("original_video")
        source_url = cleaned_data.get("source_url")

        if not original_video and not source_url:
            raise forms.ValidationError(
                "Lütfen bir video yükleyin veya bir video URL’si girin."
            )

        return cleaned_data


class UserSettingsForm(forms.ModelForm):
    """
    Ayarlar sayfasındaki kullanıcı bilgi formu.
    """
    class Meta:
        model = User
        fields = ["first_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "input-field", "placeholder": "Ad Soyad"}),
            "email": forms.EmailInput(attrs={"class": "input-field", "placeholder": "E-posta"}),
        }
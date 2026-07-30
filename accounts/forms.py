from django import forms
from django.contrib.auth.forms import AuthenticationForm

from accounts.models import get_login_code, section_code_matches


class SectionLoginForm(AuthenticationForm):
    """Login: username + password + shared institution login code."""

    login_code = forms.CharField(
        label='Nambari ya Kuingia (Taasisi)',
        strip=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nambari ya kuingia ya taasisi',
            'autocomplete': 'off',
        }),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login_code': 'Nambari ya kuingia si sahihi.',
    }

    def clean(self):
        provided = self.data.get('login_code', '')
        if not section_code_matches(provided, get_login_code()):
            raise forms.ValidationError(
                self.error_messages['invalid_login_code'],
                code='invalid_login_code',
            )
        return super().clean()

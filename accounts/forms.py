from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm

from accounts.models import login_code_is_valid, login_code_required


class SectionLoginForm(AuthenticationForm):
    """Login: username + password + shared institution login code."""

    login_code = forms.CharField(
        label='Nambari ya Kuingia (Taasisi)',
        strip=True,
        required=False,  # enforced in clean() when LUMC_LOGIN_CODE_REQUIRED
        error_messages={
            'required': 'Tafadhali weka Nambari ya Kuingia (Taasisi).',
        },
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nambari ya kuingia ya taasisi',
            'autocomplete': 'off',
        }),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': (
            'Jina la mtumiaji au nenosiri si sahihi. '
            'Jaribu tena, au badilisha nenosiri kupitia “Umesahau nenosiri?”.'
        ),
        'inactive': (
            'Akaunti bado haijaamilishwa. '
            'Wasiliana na msimamizi (System Admin) aiamilishe akaunti.'
        ),
        'invalid_login_code': (
            'Nambari ya Kuingia (Taasisi) si sahihi. '
            'Angalia nambari na ujaribu tena.'
        ),
        'missing_login_code': 'Tafadhali weka Nambari ya Kuingia (Taasisi).',
    }

    def clean(self):
        """Validate login_code before password auth so errors stay distinct.

        Also resolve username with iexact so casing differences do not fail login.
        """
        # Prefer cleaned field value; fall back to raw POST if field-level clean skipped.
        provided = ''
        if hasattr(self, 'cleaned_data') and 'login_code' in self.cleaned_data:
            provided = self.cleaned_data.get('login_code') or ''
        else:
            provided = self.data.get('login_code', '') if self.data is not None else ''

        provided = (provided or '').strip()
        if login_code_required():
            if not provided:
                raise forms.ValidationError(
                    self.error_messages['missing_login_code'],
                    code='missing_login_code',
                )
            if not login_code_is_valid(provided):
                raise forms.ValidationError(
                    self.error_messages['invalid_login_code'],
                    code='invalid_login_code',
                )

        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username is not None and password:
            UserModel = get_user_model()
            matched = UserModel._default_manager.filter(username__iexact=username).first()
            if matched is not None:
                username = matched.get_username()
                self.cleaned_data['username'] = username

            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

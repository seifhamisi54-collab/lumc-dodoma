from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from accounts.forms import SectionLoginForm


@override_settings(
    LUMC_LOGIN_CODE='LUMC-LOGIN-2026',
    LUMC_REGISTRATION_CODE='LUMC-REG-2026',
    LANGUAGE_CODE='en',
)
class SectionLoginFormUnitTests(SimpleTestCase):
    """Form-level checks (no GIS test-DB migrate required)."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch('accounts.forms.get_login_code', return_value='LUMC-LOGIN-2026')
    @patch('accounts.forms.authenticate')
    def test_wrong_login_code_does_not_authenticate(self, mock_auth, _mock_code):
        request = self.factory.post('/login/')
        form = SectionLoginForm(
            request=request,
            data={
                'username': 'DemoUser',
                'password': 'CorrectPass123!',
                'login_code': 'WRONG-CODE',
            },
        )
        self.assertFalse(form.is_valid())
        self.assertFalse(mock_auth.called)
        errors = ' '.join(str(e) for e in form.non_field_errors())
        self.assertIn('Nambari ya Kuingia', errors)
        self.assertNotIn('username and password', errors.lower())
        self.assertNotIn('Tafadhali sahihisha jina la mtumiaji', errors)

    @patch('accounts.forms.get_login_code', return_value='LUMC-LOGIN-2026')
    @patch('accounts.forms.authenticate')
    def test_missing_login_code_does_not_authenticate(self, mock_auth, _mock_code):
        request = self.factory.post('/login/')
        form = SectionLoginForm(
            request=request,
            data={
                'username': 'DemoUser',
                'password': 'CorrectPass123!',
                'login_code': '',
            },
        )
        self.assertFalse(form.is_valid())
        self.assertFalse(mock_auth.called)
        combined = ' '.join(str(e) for errs in form.errors.values() for e in errs)
        self.assertIn('Nambari ya Kuingia', combined)

    @patch('accounts.forms.get_login_code', return_value='LUMC-LOGIN-2026')
    @patch('accounts.forms.get_user_model')
    @patch('accounts.forms.authenticate')
    def test_correct_code_authenticates_with_canonical_username(
        self, mock_auth, mock_get_user_model, _mock_code
    ):
        user = MagicMock()
        user.get_username.return_value = 'DemoUser'
        user_model = MagicMock()
        user_model._default_manager.filter.return_value.first.return_value = user
        mock_get_user_model.return_value = user_model
        mock_auth.return_value = user

        request = self.factory.post('/login/')
        form = SectionLoginForm(
            request=request,
            data={
                'username': 'demouser',
                'password': 'CorrectPass123!',
                'login_code': 'LUMC-LOGIN-2026',
            },
        )
        self.assertTrue(form.is_valid())
        mock_auth.assert_called_once()
        _, kwargs = mock_auth.call_args
        self.assertEqual(kwargs['username'], 'DemoUser')
        self.assertEqual(kwargs['password'], 'CorrectPass123!')

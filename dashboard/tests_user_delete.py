"""Unit / smoke tests for System Admin delete-user (no GIS DB migrate)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.db import IntegrityError
from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase

from dashboard.system_admin_views import (
    _count_privileged_admins,
    _delete_user_safe,
    _user_is_section_head_or_super,
    api_user_detail,
)


class DeleteUserSafeUnitTests(SimpleTestCase):
    def test_self_delete_blocked(self):
        actor = MagicMock(id=7, is_superuser=True)
        target = MagicMock(id=7, username='me')
        resp = _delete_user_safe(target, actor)
        self.assertIsInstance(resp, JsonResponse)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('mwenyewe', resp.content.decode().lower())
        target.delete.assert_not_called()

    def test_non_super_cannot_delete_superuser(self):
        actor = MagicMock(id=1, is_superuser=False)
        target = MagicMock(id=2, is_superuser=True, username='root', is_active=True)
        resp = _delete_user_safe(target, actor)
        self.assertEqual(resp.status_code, 403)
        target.delete.assert_not_called()

    @patch('dashboard.system_admin_views._count_privileged_admins', return_value=0)
    @patch('dashboard.system_admin_views._user_is_section_head_or_super', return_value=True)
    def test_last_section_head_blocked(self, _is_priv, _count):
        actor = MagicMock(id=1, is_superuser=True)
        target = MagicMock(id=9, is_superuser=False, username='sole', is_active=True)
        resp = _delete_user_safe(target, actor)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('mwisho', resp.content.decode().lower())
        target.delete.assert_not_called()

    @patch('dashboard.system_admin_views.transaction')
    @patch('dashboard.system_admin_views._count_privileged_admins', return_value=2)
    @patch('dashboard.system_admin_views._user_is_section_head_or_super', return_value=False)
    def test_hard_delete_success(self, _is_priv, _count, mock_tx):
        mock_tx.atomic.return_value.__enter__ = MagicMock()
        mock_tx.atomic.return_value.__exit__ = MagicMock(return_value=False)
        actor = MagicMock(id=1, is_superuser=True)
        target = MagicMock(id=99, is_superuser=False, username='temp_to_delete', is_active=True)
        resp = _delete_user_safe(target, actor)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('success', body)
        self.assertIn('hard_deleted', body)
        target.delete.assert_called_once()

    @patch('dashboard.system_admin_views.transaction')
    @patch('dashboard.system_admin_views._count_privileged_admins', return_value=2)
    @patch('dashboard.system_admin_views._user_is_section_head_or_super', return_value=False)
    def test_integrity_error_falls_back_to_deactivate(self, _is_priv, _count, mock_tx):
        mock_tx.atomic.return_value.__enter__ = MagicMock()
        mock_tx.atomic.return_value.__exit__ = MagicMock(return_value=False)
        actor = MagicMock(id=1, is_superuser=True)
        target = MagicMock(id=55, is_superuser=False, username='fk_user', is_active=True)
        target.delete.side_effect = IntegrityError('FK')
        resp = _delete_user_safe(target, actor)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('deactivated', body)
        self.assertTrue(target.is_active is False)
        target.save.assert_called()


class DeleteUserApiPermissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _admin_user(self):
        user = MagicMock()
        user.is_authenticated = True
        user.is_superuser = True
        user.id = 1
        user.pk = 1
        return user

    def _officer_user(self):
        user = MagicMock()
        user.is_authenticated = True
        user.is_superuser = False
        user.id = 2
        user.pk = 2
        return user

    @patch('dashboard.system_admin_views.can_access_admin_panel', return_value=False)
    def test_non_privileged_forbidden_at_admin_gate(self, _cap):
        request = self.factory.delete('/api/system-admin/users/9/')
        request.user = self._officer_user()
        resp = api_user_detail(request, 9)
        self.assertEqual(resp.status_code, 403)

    @patch('dashboard.system_admin_views._delete_user_safe')
    @patch('dashboard.system_admin_views.can_manage_users', return_value=True)
    @patch('dashboard.system_admin_views.can_access_admin_panel', return_value=True)
    @patch('dashboard.system_admin_views.User')
    def test_privileged_delete_wires_safe_helper(self, mock_user_model, _cap, _cmu, mock_safe):
        target = MagicMock()
        target.id = 9
        mock_user_model.objects.select_related.return_value.get.return_value = target
        mock_safe.return_value = JsonResponse({'status': 'success', 'deleted': 9})

        request = self.factory.delete('/api/system-admin/users/9/')
        request.user = self._admin_user()
        resp = api_user_detail(request, 9)
        self.assertEqual(resp.status_code, 200)
        mock_safe.assert_called_once_with(target, request.user)

    @patch('dashboard.system_admin_views.can_manage_users', return_value=False)
    @patch('dashboard.system_admin_views.can_access_admin_panel', return_value=True)
    @patch('dashboard.system_admin_views.User')
    def test_admin_panel_without_manage_users_cannot_delete(self, mock_user_model, _cap, _cmu):
        target = MagicMock()
        mock_user_model.objects.select_related.return_value.get.return_value = target
        request = self.factory.delete('/api/system-admin/users/9/')
        request.user = self._officer_user()
        resp = api_user_detail(request, 9)
        self.assertEqual(resp.status_code, 403)
        self.assertIn('ruhusa', resp.content.decode().lower())


class PrivilegedAdminHelpersTests(SimpleTestCase):
    def test_inactive_user_not_privileged(self):
        user = MagicMock(is_active=False, is_superuser=True)
        self.assertFalse(_user_is_section_head_or_super(user))

    def test_active_superuser_is_privileged(self):
        user = MagicMock(is_active=True, is_superuser=True)
        self.assertTrue(_user_is_section_head_or_super(user))

    @patch('dashboard.system_admin_views.User')
    def test_count_excludes_id(self, mock_user_model):
        qs = MagicMock()
        mock_user_model.objects.filter.return_value.filter.return_value = qs
        qs.exclude.return_value.distinct.return_value.count.return_value = 1
        self.assertEqual(_count_privileged_admins(exclude_id=5), 1)
        qs.exclude.assert_called_once_with(pk=5)

"""Weka upya password ya mtumiaji wa Django GIS Portal.

Mfano:
  python scripts/reset_password.py seif17 Nlupc2026
"""

import os
import sys

import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tanzania_gis.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3:
        print("Matumizi: python scripts/reset_password.py <username> <password_mpya>")
        raise SystemExit(1)

    username, password = sys.argv[1], sys.argv[2]
    if len(password) < 6:
        raise SystemExit("Password lazima iwe angalau herufi 6.")

    User = get_user_model()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        names = list(User.objects.values_list("username", flat=True)[:20])
        print("Watumiaji (baadhi):", ", ".join(names))
        raise SystemExit(f"Mtumiaji '{username}' haipatikani.")

    user.set_password(password)
    user.save()
    print(f"Password ya '{username}' imewekwa upya (Django GIS Portal).")


if __name__ == "__main__":
    main()

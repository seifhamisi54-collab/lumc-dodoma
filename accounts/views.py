"""Authentication helpers — password reset for LUMC Section (bila SMTP)."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods


User = get_user_model()


@require_http_methods(['GET', 'POST'])
def password_reset_view(request):
    """
    Reset nenosiri kwa username (+ email ikiwa ipo kwenye akaunti).
    Haitumii SMTP — inafaa kwa Lumc Section Database.
    """
    context = {
        'error': '',
        'success': False,
        'username': '',
        'email': '',
    }

    if request.method == 'GET':
        return render(request, 'registration/password_reset_form.html', context)

    username = (request.POST.get('username') or '').strip()
    email = (request.POST.get('email') or '').strip()
    password1 = request.POST.get('password1') or ''
    password2 = request.POST.get('password2') or ''
    context.update({'username': username, 'email': email})

    if not username:
        context['error'] = 'Jaza username.'
        return render(request, 'registration/password_reset_form.html', context, status=400)

    if not password1 or not password2:
        context['error'] = 'Jaza nenosiri jipya mara mbili.'
        return render(request, 'registration/password_reset_form.html', context, status=400)

    if password1 != password2:
        context['error'] = 'Nenosiri halifanani. Jaribu tena.'
        return render(request, 'registration/password_reset_form.html', context, status=400)

    user = User.objects.filter(username__iexact=username).first()
    if user is None:
        # Usitoe kama username haipo (salama kidogo) — ujumbe wa jumla
        context['error'] = 'Username au email si sahihi.'
        return render(request, 'registration/password_reset_form.html', context, status=400)

    stored_email = (user.email or '').strip()
    if stored_email:
        if not email or email.lower() != stored_email.lower():
            context['error'] = 'Username au email si sahihi.'
            return render(request, 'registration/password_reset_form.html', context, status=400)
    # Ikiwa akaunti haina email, username pekee inatosha

    if not user.is_active:
        context['error'] = 'Akaunti haijaamilishwa. Wasiliana na msimamizi.'
        return render(request, 'registration/password_reset_form.html', context, status=400)

    try:
        validate_password(password1, user=user)
    except ValidationError as exc:
        context['error'] = ' '.join(exc.messages)
        return render(request, 'registration/password_reset_form.html', context, status=400)

    user.set_password(password1)
    user.save(update_fields=['password'])
    messages.success(request, 'Nenosiri limebadilishwa. Ingia kwa nenosiri jipya.')
    return redirect('login')

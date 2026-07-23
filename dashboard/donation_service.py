"""
Huduma ya michango — Kadi (Stripe) na Pay Merchant (Pesapal).
"""
import json
import secrets
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.utils import timezone

from dashboard.models import DownloadDonation


def _donation_settings():
    return getattr(settings, 'DONATION_SETTINGS', {})


def _site_base_url(request=None):
    if request:
        return request.build_absolute_uri('/').rstrip('/')
    return _donation_settings().get('SITE_URL', 'http://localhost:8000').rstrip('/')


def _generate_reference():
    return 'DON-' + secrets.token_hex(6).upper()


def _http_post_form(url, payload, headers=None):
    """POST application/x-www-form-urlencoded (kwa Stripe API)."""
    import urllib.parse

    def _flatten(data, prefix=''):
        pairs = []
        for key, value in data.items():
            full_key = f'{prefix}[{key}]' if prefix else key
            if isinstance(value, dict):
                pairs.extend(_flatten(value, full_key))
            elif isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, dict):
                        pairs.extend(_flatten(item, f'{full_key}[{idx}]'))
                    elif item is not None:
                        pairs.append((f'{full_key}[{idx}]', item))
            elif value is not None:
                pairs.append((full_key, value))
        return pairs

    body = urllib.parse.urlencode(_flatten(payload)).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            **(headers or {}),
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _http_post_json(url, payload, headers=None):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json', **(headers or {})},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _http_get_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {}, method='GET')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def validate_donation_payload(data):
    try:
        amount = Decimal(str(data.get('amount', '0')))
    except (InvalidOperation, TypeError):
        raise ValueError('Kiasi cha mchango si sahihi.')

    if amount <= 0:
        raise ValueError('Weka kiasi cha mchango zaidi ya 0.')
    if amount > Decimal('100000000'):
        raise ValueError('Kiasi cha mchango ni kikubwa mno.')

    currency = (data.get('currency') or 'TZS').upper()
    if currency not in ('TZS', 'USD'):
        raise ValueError('Sarafu inayotumika ni TZS au USD tu.')

    method = (data.get('payment_method') or 'card').lower()
    if method not in ('card', 'merchant'):
        raise ValueError('Njia ya malipo si sahihi.')

    data_type = (data.get('data_type') or '').strip()
    fmt = (data.get('format') or '').strip()
    if not data_type or not fmt:
        raise ValueError('Chagua aina ya data na format ya kupakua.')

    return amount, currency, method, data_type, fmt


def create_donation(request, data):
    amount, currency, method, data_type, fmt = validate_donation_payload(data)

    donation = DownloadDonation.objects.create(
        reference=_generate_reference(),
        user=request.user if request.user.is_authenticated else None,
        amount=amount,
        currency=currency,
        payment_method=method,
        download_data_type=data_type,
        download_format=fmt,
        download_region=(data.get('region') or '').strip(),
        download_district=(data.get('district') or '').strip(),
        download_ward=(data.get('ward') or '').strip(),
        payer_name=(data.get('payer_name') or '').strip(),
        payer_email=(data.get('payer_email') or '').strip(),
        payer_phone=(data.get('payer_phone') or '').strip(),
    )

    cfg = _donation_settings()
    base = _site_base_url(request)

    if method == 'card' and cfg.get('STRIPE_SECRET_KEY'):
        return _initiate_stripe(donation, base, cfg)
    if method == 'merchant' and cfg.get('PESAPAL_CONSUMER_KEY'):
        return _initiate_pesapal(donation, base, cfg)

    # Demo / fallback — ukurasa wa malipo wa ndani
    donation.provider = 'demo'
    donation.save(update_fields=['provider'])
    return {
        'success': True,
        'reference': donation.reference,
        'provider': 'demo',
        'payment_url': f'{base}/donation/lipa/{donation.reference}/',
        'message': 'Elekea ukurasa wa malipo kukamilisha mchango.',
    }


def _initiate_stripe(donation, base_url, cfg):
    secret = cfg['STRIPE_SECRET_KEY']
    currency_code = donation.currency.lower()
    amount_cents = int(donation.amount * 100)
    if currency_code == 'tzs':
        amount_cents = int(donation.amount)  # TZS haina desimali kwa Stripe

    success_url = (
        f'{base_url}/donation/imethibitishwa/{donation.reference}/'
        f'?session_id={{CHECKOUT_SESSION_ID}}'
    )
    cancel_url = f'{base_url}/donation/lipa/{donation.reference}/?cancelled=1'

    payload = {
        'mode': 'payment',
        'success_url': success_url,
        'cancel_url': cancel_url,
        'client_reference_id': donation.reference,
        'customer_email': donation.payer_email or None,
        'line_items': [{
            'quantity': 1,
            'price_data': {
                'currency': currency_code,
                'unit_amount': amount_cents,
                'product_data': {
                    'name': 'Mchango — Tanzania GIS Data Download',
                    'description': f'Pakua {donation.download_data_type} ({donation.download_format})',
                },
            },
        }],
        'metadata': {'donation_reference': donation.reference},
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        result = _http_post_form(
            'https://api.stripe.com/v1/checkout/sessions',
            payload,
            headers={'Authorization': f'Bearer {secret}'},
        )
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise ValueError(f'Stripe: {body}') from e

    donation.provider = 'stripe'
    donation.provider_reference = result.get('id', '')
    donation.save(update_fields=['provider', 'provider_reference'])

    return {
        'success': True,
        'reference': donation.reference,
        'provider': 'stripe',
        'payment_url': result['url'],
    }


def _pesapal_token(cfg):
    url = cfg.get('PESAPAL_BASE_URL', 'https://pay.pesapal.com/v3') + '/api/Auth/RequestToken'
    result = _http_post_json(url, {
        'consumer_key': cfg['PESAPAL_CONSUMER_KEY'],
        'consumer_secret': cfg['PESAPAL_CONSUMER_SECRET'],
    })
    return result.get('token')


def _initiate_pesapal(donation, base_url, cfg):
    token = _pesapal_token(cfg)
    if not token:
        raise ValueError('Imeshindwa kupata token ya Pesapal.')

    base = cfg.get('PESAPAL_BASE_URL', 'https://pay.pesapal.com/v3')
    callback = f'{base_url}/donation/pesapal-callback/'
    payload = {
        'id': donation.reference,
        'currency': donation.currency,
        'amount': float(donation.amount),
        'description': f'Mchango GIS — {donation.download_data_type}',
        'callback_url': callback,
        'redirect_url': f'{base_url}/donation/imethibitishwa/{donation.reference}/',
        'billing_address': {
            'email_address': donation.payer_email or 'donor@example.com',
            'phone_number': donation.payer_phone or '',
            'first_name': donation.payer_name or 'Mchangiaji',
            'last_name': 'GIS',
        },
    }

    try:
        result = _http_post_json(
            f'{base}/api/Transactions/SubmitOrderRequest',
            payload,
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
        )
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise ValueError(f'Pesapal: {body}') from e

    redirect_url = result.get('redirect_url') or result.get('order_tracking_id')
    tracking_id = result.get('order_tracking_id', '')

    donation.provider = 'pesapal'
    donation.provider_reference = tracking_id
    donation.save(update_fields=['provider', 'provider_reference'])

    return {
        'success': True,
        'reference': donation.reference,
        'provider': 'pesapal',
        'payment_url': redirect_url,
    }


def mark_donation_paid(donation):
    if donation.status == 'paid':
        return donation
    donation.status = 'paid'
    donation.paid_at = timezone.now()
    donation.save(update_fields=['status', 'paid_at'])
    return donation


def verify_stripe_session(donation, session_id, cfg):
    if not session_id or not cfg.get('STRIPE_SECRET_KEY'):
        return False
    try:
        result = _http_get_json(
            f'https://api.stripe.com/v1/checkout/sessions/{session_id}',
            headers={'Authorization': f'Bearer {cfg["STRIPE_SECRET_KEY"]}'},
        )
        return result.get('payment_status') == 'paid'
    except Exception:
        return False


def complete_demo_payment(donation, card_last4=None):
    donation.provider_reference = card_last4 or 'DEMO-OK'
    return mark_donation_paid(donation)

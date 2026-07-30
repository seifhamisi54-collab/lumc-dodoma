# Convert legacy choice codes → free-text Swahili labels

from django.db import migrations


SOURCE_LABELS = {
    'unclear_boundary': 'Mipaka isiyoeleweka',
    'no_documents': 'Ukosefu wa hati / usajili',
    'inheritance_dispute': 'Mgogoro wa urithi',
    'land_grabbing': 'Kunyakua ardhi',
    'population_pressure': 'Msongamano wa watu',
    'resource_competition': 'Ushindani wa rasilimali',
    'resettlement': 'Uhamishaji / makazi mapya',
    'investor_project': 'Mradi wa uwekezaji',
    'admin_decision': 'Uamuzi wa utawala',
    'other': 'Chanzo kingine',
}

METHOD_LABELS = {
    'mediation': 'Usuluhishi wa kijamii',
    'village_council': 'Baraza la Kijiji',
    'ward_tribunal': 'Baraza la Kata',
    'district_land': 'Ofisi ya Ardhi ya Wilaya',
    'court': 'Mahakama',
    'negotiation': 'Majadiliano',
    'survey': 'Upimaji / mipaka mpya',
    'compensation': 'Fidia',
    'other': 'Nyingine',
    'none': '',
}


def convert_choice_codes_to_labels(apps, schema_editor):
    Case = apps.get_model('land_conflicts', 'LandConflictCase')
    for case in Case.objects.all().iterator():
        changed = False
        src = (case.conflict_source or '').strip()
        if src in SOURCE_LABELS:
            case.conflict_source = SOURCE_LABELS[src]
            changed = True
        method = (case.resolution_method or '').strip()
        if method in METHOD_LABELS:
            label = METHOD_LABELS[method]
            details = (case.resolution_details or '').strip()
            if label and details and label != details:
                case.resolution_method = f'{label}\n{details}'
            else:
                case.resolution_method = label or details
            changed = True
        if changed:
            case.save(update_fields=['conflict_source', 'resolution_method'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('land_conflicts', '0010_free_text_chanzo_utatuzi'),
    ]

    operations = [
        migrations.RunPython(convert_choice_codes_to_labels, noop_reverse),
    ]

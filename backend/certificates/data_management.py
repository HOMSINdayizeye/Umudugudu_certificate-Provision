"""System admin data management: count, and delete in bulk, the records and stored files each part of the
system produces. Reference data (locations), accounts of administrators, role policies and settings are
never touched here."""
import datetime
import os

from django.core.files.storage import default_storage
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    CustomUser, CertificateRequest, RequestAttachment, Notification, Announcement, Activity, Attendance,
    ServicePayment, CitizenTransfer, DeathReport, Citizen,
)

# Storage folders the models write into; anything else under MEDIA is left alone
MEDIA_FOLDERS = ('generated', 'attachments', 'announcements')
# The phrase the admin must type before anything is deleted
CONFIRM_PHRASE = 'DELETE'


def _before(qs, field, before):
    return qs.filter(**{f'{field}__lt': before}) if before else qs


def _file_names(qs, field):
    return [name for name in qs.exclude(**{field: ''}).exclude(**{f'{field}__isnull': True})
            .values_list(field, flat=True) if name]


def _delete_files(names):
    """Remove stored files, returning (count, bytes); a file already gone is not an error."""
    count = freed = 0
    for name in names:
        try:
            freed += default_storage.size(name)
        except Exception:
            pass
        try:
            default_storage.delete(name)
            count += 1
        except Exception:
            pass
    return count, freed


def _request_files(requests_qs):
    names = _file_names(requests_qs, 'generated_document')
    names += _file_names(RequestAttachment.objects.filter(request__in=requests_qs), 'file')
    return names


def _accounts_qs(admin):
    # Every non-administrator account other than the one doing the deleting
    return CustomUser.objects.filter(is_superuser=False).exclude(role='system_admin').exclude(pk=admin.pk)


def _deceased_qs():
    return Citizen.objects.filter(Q(status='deceased') | Q(death_report__isnull=False))


# ---------- Dataset definitions ----------
# Each dataset: how to count (rows, files) under an optional cutoff date, and how to purge it.

def _simple(model, date_field, file_field=None, extra_files=None):
    def query(before, admin):
        return _before(model.objects.all(), date_field, before)

    def count(before, admin):
        qs = query(before, admin)
        files = len(_file_names(qs, file_field)) if file_field else 0
        if extra_files:
            files += len(extra_files(qs))
        return qs.count(), files

    def purge(before, admin):
        qs = query(before, admin)
        names = _file_names(qs, file_field) if file_field else []
        if extra_files:
            names += extra_files(qs)
        rows, _ = qs.delete()
        files, freed = _delete_files(names)
        return rows, files, freed

    return count, purge


def _letters_count(before, admin):
    qs = _before(CertificateRequest.objects.exclude(generated_document=''), 'created_at', before)
    n = len(_file_names(qs, 'generated_document'))
    return n, n


def _letters_purge(before, admin):
    # Files only: the requests stay and a leader can regenerate any letter later
    qs = _before(CertificateRequest.objects.exclude(generated_document=''), 'created_at', before)
    names = _file_names(qs, 'generated_document')
    qs.update(generated_document='')
    files, freed = _delete_files(names)
    return 0, files, freed


def _accounts_count(before, admin):
    qs = _before(_accounts_qs(admin), 'date_joined', before)
    return qs.count(), len(_request_files(CertificateRequest.objects.filter(user__in=qs)))


def _accounts_purge(before, admin):
    qs = _before(_accounts_qs(admin), 'date_joined', before)
    names = _request_files(CertificateRequest.objects.filter(user__in=qs))
    rows, _ = qs.delete()
    files, freed = _delete_files(names)
    return rows, files, freed


def _deaths_count(before, admin):
    return _before(_deceased_qs(), 'death_report__reported_at', before).count(), 0


def _deaths_purge(before, admin):
    rows, _ = _before(_deceased_qs(), 'death_report__reported_at', before).delete()
    return rows, 0, 0


def _all_stored_files():
    """Every file under the media folders the app writes to (works for disk and bucket storage)."""
    names = []

    def walk(folder):
        try:
            dirs, files = default_storage.listdir(folder)
        except Exception:
            return
        names.extend(f'{folder}/{f}' for f in files)
        for d in dirs:
            walk(f'{folder}/{d}')

    for folder in MEDIA_FOLDERS:
        walk(folder)
    return names


def _referenced_files():
    refs = set(_file_names(CertificateRequest.objects.all(), 'generated_document'))
    refs |= set(_file_names(RequestAttachment.objects.all(), 'file'))
    refs |= set(_file_names(Announcement.objects.all(), 'generated_document'))
    return {r.replace('\\', '/') for r in refs}


def _orphan_files():
    refs = _referenced_files()
    return [n for n in _all_stored_files() if n not in refs]


def _orphans_count(before, admin):
    n = len(_orphan_files())
    return 0, n


def _orphans_purge(before, admin):
    files, freed = _delete_files(_orphan_files())
    return 0, files, freed


_req_count, _req_purge = _simple(CertificateRequest, 'created_at', 'generated_document',
                                 lambda qs: _file_names(RequestAttachment.objects.filter(request__in=qs), 'file'))
_att_count, _att_purge = _simple(RequestAttachment, 'uploaded_at', 'file')
_notif_count, _notif_purge = _simple(Notification, 'created_at')
_ann_count, _ann_purge = _simple(Announcement, 'created_at', 'generated_document')
_act_count, _act_purge = _simple(Activity, 'created_at')
_attend_count, _attend_purge = _simple(Attendance, 'marked_at')
_pay_count, _pay_purge = _simple(ServicePayment, 'paid_at')
_tr_count, _tr_purge = _simple(CitizenTransfer, 'transferred_at')
_cit_count, _cit_purge = _simple(Citizen, 'created_at')

DATASETS = [
    {'key': 'requests', 'label': 'Certificate requests', 'group': 'Requests & letters',
     'description': 'Every certificate request with its letter, attachments, codes and related notifications.',
     'count': _req_count, 'purge': _req_purge, 'dated': True},
    {'key': 'letters', 'label': 'Generated letters (files only)', 'group': 'Requests & letters',
     'description': 'The .docx letters stored for approved requests. Requests are kept; a leader can regenerate a letter.',
     'count': _letters_count, 'purge': _letters_purge, 'dated': True},
    {'key': 'attachments', 'label': 'Request attachments', 'group': 'Requests & letters',
     'description': 'Files citizens uploaded with their requests (ID copies, proofs, photos).',
     'count': _att_count, 'purge': _att_purge, 'dated': True},
    {'key': 'notifications', 'label': 'Notifications', 'group': 'Communications',
     'description': 'In-app notices sent to users (letter issued, transfer awaiting confirmation…).',
     'count': _notif_count, 'purge': _notif_purge, 'dated': True},
    {'key': 'announcements', 'label': 'Announcements', 'group': 'Communications',
     'description': 'Leader announcements and their rendered letters.',
     'count': _ann_count, 'purge': _ann_purge, 'dated': True},
    {'key': 'activities', 'label': 'Activities', 'group': 'Community',
     'description': 'Community activities together with every attendance marked for them.',
     'count': _act_count, 'purge': _act_purge, 'dated': True},
    {'key': 'attendances', 'label': 'Attendance records', 'group': 'Community',
     'description': 'Attendance marks only; the activities themselves stay.',
     'count': _attend_count, 'purge': _attend_purge, 'dated': True},
    {'key': 'payments', 'label': 'Service payments', 'group': 'Community',
     'description': 'Cleaning and security payment records.',
     'count': _pay_count, 'purge': _pay_purge, 'dated': True},
    {'key': 'transfers', 'label': 'Citizen transfers', 'group': 'Citizens',
     'description': 'The history of citizens moved between villages. Citizens stay where they are now.',
     'count': _tr_count, 'purge': _tr_purge, 'dated': True},
    {'key': 'deaths', 'label': 'Deceased citizens', 'group': 'Citizens',
     'description': 'Death reports together with the deceased citizens\' registry records.',
     'count': _deaths_count, 'purge': _deaths_purge, 'dated': True},
    {'key': 'citizens', 'label': 'Citizen registry', 'group': 'Citizens',
     'description': 'Every registry citizen, with their payments, attendances, transfers and death reports.',
     'count': _cit_count, 'purge': _cit_purge, 'dated': True},
    {'key': 'accounts', 'label': 'User accounts (non-admin)', 'group': 'Accounts',
     'description': 'Citizen, leader and volunteer accounts with everything they own. Administrators and your own account are kept.',
     'count': _accounts_count, 'purge': _accounts_purge, 'dated': True},
    {'key': 'orphan_files', 'label': 'Unreferenced files', 'group': 'Storage',
     'description': 'Files left in storage that no request, attachment or announcement points to any more.',
     'count': _orphans_count, 'purge': _orphans_purge, 'dated': False},
]
DATASET_KEYS = [d['key'] for d in DATASETS]
# Deleting parents first means the child datasets report 0 instead of being counted twice
PURGE_ORDER = ['accounts', 'requests', 'letters', 'attachments', 'notifications', 'announcements', 'citizens',
               'deaths', 'transfers', 'activities', 'attendances', 'payments', 'orphan_files']


def parse_before(value):
    """'YYYY-MM-DD' → aware datetime at the start of that day (Kigali time), None when blank."""
    if not value:
        return None
    day = datetime.date.fromisoformat(str(value))
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))


def database_size():
    """Bytes the database occupies (Postgres) or the size of the SQLite file; None when unknown."""
    try:
        if connection.vendor == 'postgresql':
            with connection.cursor() as cur:
                cur.execute('SELECT pg_database_size(current_database())')
                return cur.fetchone()[0]
        if connection.vendor == 'sqlite':
            return os.path.getsize(connection.settings_dict['NAME'])
    except Exception:
        return None
    return None


def storage_usage():
    names = _all_stored_files()
    total = 0
    for name in names:
        try:
            total += default_storage.size(name)
        except Exception:
            pass
    return {'files': len(names), 'bytes': total}


def overview(admin, before=None):
    rows = []
    for d in DATASETS:
        n_rows, n_files = d['count'](before if d['dated'] else None, admin)
        rows.append({'key': d['key'], 'label': d['label'], 'group': d['group'], 'description': d['description'],
                     'rows': n_rows, 'files': n_files, 'dated': d['dated']})
    return {
        'datasets': rows,
        'database_bytes': database_size(),
        'storage': storage_usage(),
        'before': before.date().isoformat() if before else None,
        'confirm_phrase': CONFIRM_PHRASE,
    }


def purge(admin, keys, before=None):
    """Delete the chosen datasets; returns per-dataset results and totals."""
    chosen = [k for k in PURGE_ORDER if k in set(keys)]
    results = []
    total_rows = total_files = total_bytes = 0
    for key in chosen:
        d = next(x for x in DATASETS if x['key'] == key)
        with transaction.atomic():
            rows, files, freed = d['purge'](before if d['dated'] else None, admin)
        results.append({'key': key, 'label': d['label'], 'rows': rows, 'files': files, 'bytes': freed})
        total_rows += rows
        total_files += files
        total_bytes += freed
    return {'results': results, 'rows': total_rows, 'files': total_files, 'bytes': total_bytes}

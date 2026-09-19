"""Permission catalog and resolution (role defaults + admin overrides), modelled on cok_systems' resources/roles."""

# Every action the system can grant, grouped by resource. Keys are "action:resource".
CATALOG = [
    {
        'resource': 'citizens', 'label': 'Citizens',
        'actions': [
            ('view:citizens', 'View the citizens of their area'),
            ('add:citizens', 'Register new citizens'),
            ('edit:citizens', 'Edit citizen information'),
            ('delete:citizens', 'Delete a citizen record'),
            ('transfer:citizens', 'Transfer a citizen to another village'),
            ('place:citizens', 'Place a transferred citizen in an isibo'),
            ('view:transfers', 'View citizens transferred in and out of their area'),
            ('report:deaths', 'Report a citizen as deceased (registering them first if needed)'),
            ('view:deaths', 'View the deceased register of their area'),
        ],
    },
    {
        'resource': 'activities', 'label': 'Activities & attendance',
        'actions': [
            ('view:activities', 'View activities and attendance in their area'),
            ('create:activities', 'Create and edit activities (community work, meetings, elections…)'),
            ('mark:attendance', 'Mark attendance, registering citizens on the spot when needed'),
        ],
    },
    {
        'resource': 'payments', 'label': 'Service payments',
        'actions': [
            ('view:payments', 'View cleaning and security payments'),
            ('record:payments', 'Mark and unmark service payments'),
        ],
    },
    {
        'resource': 'requests', 'label': 'Certificate requests',
        'actions': [
            ('approve:requests', 'Approve or deny certificate requests in their area'),
        ],
    },
    {
        'resource': 'announcements', 'label': 'Announcements',
        'actions': [
            ('create:announcements', 'Write and publish announcements'),
        ],
    },
    {
        'resource': 'users', 'label': 'User accounts',
        'actions': [
            ('view:users', 'View all user accounts'),
            ('add:users', 'Create user accounts'),
            ('delete:users', 'Delete user accounts'),
            ('eligibility:users', 'Mark users eligible or not eligible'),
            ('permissions:users', 'Manage roles and permissions'),
            ('settings:attendance', 'Set the attendance count required for a community engagement letter'),
        ],
    },
]

ALL_KEYS = [key for group in CATALOG for key, _ in group['actions']]

_ACTIVITIES = ['view:activities', 'create:activities', 'mark:attendance']
_LEADER = ['view:citizens', 'transfer:citizens', 'place:citizens', 'view:transfers', 'view:deaths', 'view:payments',
           'approve:requests', 'create:announcements'] + _ACTIVITIES
_VOLUNTEER = ['view:citizens', 'view:payments', 'record:payments']

# What each role can do until the admin changes it on the Roles page
ROLE_DEFAULTS = {
    'citizen': [],
    'isibo_leader': ['view:citizens', 'add:citizens', 'edit:citizens'] + _ACTIVITIES,
    # Only the village leader reports deaths; cell and sector leaders view the register
    'village_leader': _LEADER + ['report:deaths'],
    'cell_leader': list(_LEADER),
    'sector_leader': ['view:citizens', 'view:transfers', 'view:deaths', 'view:payments', 'approve:requests',
                      'create:announcements'] + _ACTIVITIES,
    'security_volunteer': list(_VOLUNTEER),
    'cleaning_volunteer': list(_VOLUNTEER),
    'system_admin': list(ALL_KEYS),
}


def clean_keys(keys):
    """Keep only known permission keys, deduplicated, in catalog order."""
    wanted = set(keys or [])
    return [k for k in ALL_KEYS if k in wanted]


def is_full_admin(user):
    return bool(user) and (user.is_superuser or user.role == 'system_admin')


def role_permissions(role):
    """The role's current permission set: the admin's saved policy, else the built-in defaults."""
    from .models import RolePolicy
    policy = RolePolicy.objects.filter(role=role).first()
    if policy is not None:
        return clean_keys(policy.permissions)
    return list(ROLE_DEFAULTS.get(role, []))


def effective_permissions(user):
    """Administrators hold everything; others get (role policy + grants) - denies."""
    if is_full_admin(user):
        return list(ALL_KEYS)
    keys = set(role_permissions(user.role)) | set(user.permission_grants or [])
    keys -= set(user.permission_denies or [])
    return clean_keys(keys)


def has_perm(user, key):
    return key in effective_permissions(user)

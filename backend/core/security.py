from .models import DatiCampagna, Giocatore


ROLE_HIERARCHY = [
    {
        "id": Giocatore.ROLE_USER,
        "label": "Giocatore",
        "rank": Giocatore.ROLE_RANKS[Giocatore.ROLE_USER],
        "description": "Preferenze personali per aspetto, accessibilità, dadi e interfaccia.",
    },
    {
        "id": Giocatore.ROLE_MASTER,
        "label": "Master",
        "rank": Giocatore.ROLE_RANKS[Giocatore.ROLE_MASTER],
        "description": "Comprende le preferenze personali e gli strumenti di gestione della sessione.",
    },
    {
        "id": Giocatore.ROLE_ADMIN,
        "label": "Amministratore",
        "rank": Giocatore.ROLE_RANKS[Giocatore.ROLE_ADMIN],
        "description": "Controllo completo di temi, identità, sicurezza, funzioni e configurazione globale.",
    },
]


def get_or_create_giocatore_for_user(user) -> Giocatore:
    default_role = Giocatore.ROLE_MASTER if user.username == "local_master" else Giocatore.ROLE_USER
    giocatore, _ = Giocatore.objects.get_or_create(
        nome=user.username,
        defaults={
            "display_name": user.username.replace("_", " ").title(),
            "role": default_role,
            "active_campaign": DatiCampagna.objects.filter(
                archived_at__isnull=True,
                attiva=True,
            ).first(),
        },
    )
    return giocatore


def effective_role(user, giocatore: Giocatore) -> str:
    if giocatore.role in Giocatore.ROLE_RANKS:
        return giocatore.role
    return Giocatore.ROLE_USER


def role_rank(role: str) -> int:
    return Giocatore.ROLE_RANKS.get(role, 0)


def has_minimum_role(role: str, required_role: str) -> bool:
    return role_rank(role) >= role_rank(required_role)


def security_payload(user, giocatore: Giocatore) -> dict:
    role = effective_role(user, giocatore)
    # Django staff permissions and game permissions are intentionally separate.
    # A Django administrator may use the game as a Giocatore or Master.
    show_admin_link = bool(user.is_staff or user.is_superuser)
    return {
        "role": role,
        "roleRank": role_rank(role),
        "hierarchy": ROLE_HIERARCHY if role == Giocatore.ROLE_ADMIN else [],
        "showRoleLabels": role == Giocatore.ROLE_ADMIN,
        "showAdminLink": show_admin_link,
        "canUseDjangoAdmin": show_admin_link,
        "canManageMasterSettings": has_minimum_role(role, Giocatore.ROLE_MASTER),
        "canManageGameData": has_minimum_role(role, Giocatore.ROLE_MASTER),
        "canManageAdminSettings": has_minimum_role(role, Giocatore.ROLE_ADMIN),
        "adminUrl": "/admin/",
    }

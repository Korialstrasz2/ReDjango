BACKUP_ENABLED_SETTING_KEY = "backup.enabled"
BACKUP_ON_STARTUP_SETTING_KEY = "backup.on_startup"
BACKUP_INTERVAL_SETTING_KEY = "backup.interval_minutes"
BACKUP_RETENTION_SETTING_KEY = "backup.retention_count"

BACKUP_SETTING_KEYS = (
    BACKUP_ENABLED_SETTING_KEY,
    BACKUP_ON_STARTUP_SETTING_KEY,
    BACKUP_INTERVAL_SETTING_KEY,
    BACKUP_RETENTION_SETTING_KEY,
)

BACKUP_SETTING_DEFINITIONS = (
    {
        "key": BACKUP_ENABLED_SETTING_KEY,
        "label": "Backup automatici",
        "category": "backup",
        "description": "Attiva le copie automatiche del database di ReDjango.",
        "minimum_role": "admin",
        "value_type": "bool",
        "default_value": True,
        "choices": [],
        "user_customizable": False,
        "master_customizable": False,
        "order": 10,
    },
    {
        "key": BACKUP_ON_STARTUP_SETTING_KEY,
        "label": "Backup all'avvio del server",
        "category": "backup",
        "description": "Crea una copia quando il processo server di ReDjango viene avviato.",
        "minimum_role": "admin",
        "value_type": "bool",
        "default_value": True,
        "choices": [],
        "user_customizable": False,
        "master_customizable": False,
        "order": 20,
    },
    {
        "key": BACKUP_INTERVAL_SETTING_KEY,
        "label": "Intervallo backup automatico",
        "category": "backup",
        "description": "Minuti di attività del server tra due backup automatici.",
        "minimum_role": "admin",
        "value_type": "int",
        "default_value": 30,
        "choices": [],
        "user_customizable": False,
        "master_customizable": False,
        "order": 30,
        "validation": {"minimum": 5, "maximum": 120, "step": 1},
    },
    {
        "key": BACKUP_RETENTION_SETTING_KEY,
        "label": "Numero massimo di backup",
        "category": "backup",
        "description": "Conserva le copie più recenti create da Gestione Backup e rimuove quelle più vecchie.",
        "minimum_role": "admin",
        "value_type": "int",
        "default_value": 12,
        "choices": [],
        "user_customizable": False,
        "master_customizable": False,
        "order": 40,
        "validation": {"minimum": 1, "maximum": 100, "step": 1},
    },
)

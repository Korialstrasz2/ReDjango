"""Elenco delle superfici che un tema può vestire con uno sfondo dedicato.

Ogni pagina, modale e strumento rapido ha la propria voce: nessuna superficie
eredita lo sfondo di un'altra. Chi cura il tema sceglie immagine per immagine e,
se vuole lo stesso sfondo su più schermate, riusa la stessa immagine.

Le superfici vivono qui e non come colonne del modello Theme: aggiungere una
pagina o una modale è una riga in questo file, senza migrazioni. Le sezioni
servono solo a raggruppare i campi nell'editor dei temi.

Questo modulo non importa nulla da Django: modelli, migrazioni, seed e
selettori possono usarlo liberamente.
"""

# Le sezioni in cui l'editor raggruppa le superfici, nell'ordine di comparsa.
THEME_SURFACE_SECTIONS = [
    {
        "key": "pagine",
        "label": "Pagine",
        "description": "Le schermate principali raggiungibili dal menu laterale.",
    },
    {
        "key": "modali",
        "label": "Modali",
        "description": "Le finestre che si aprono sopra le pagine dei giocatori.",
    },
    {
        "key": "strumenti-rapidi",
        "label": "Strumenti rapidi",
        "description": "I pannelli della barra in alto: diario, dadi, AI, audio e furto.",
    },
    {
        "key": "strumenti",
        "label": "Strumenti",
        "description": "L'area riservata a Master e amministratori usa un unico sfondo.",
    },
]

# key: identificatore usato dal frontend · label: nome mostrato nell'editor
# section: sezione dell'editor · hint: dove si incontra la superficie
THEME_SURFACES = [
    # --- Pagine -------------------------------------------------------------
    {"key": "dashboard", "label": "Sala principale", "section": "pagine", "hint": "La schermata iniziale."},
    {"key": "personaggio", "label": "Scheda personaggio", "section": "pagine", "hint": "La scheda di un singolo personaggio."},
    {"key": "skills", "label": "Abilità", "section": "pagine", "hint": "Il grimorio delle abilità."},
    {"key": "competencies", "label": "Competenze", "section": "pagine", "hint": "L'albero delle competenze."},
    {"key": "creation", "label": "Creazione", "section": "pagine", "hint": "La creazione di un nuovo personaggio."},
    {"key": "combat", "label": "Combattimento", "section": "pagine", "hint": "Il tavolo tattico."},
    {"key": "travel", "label": "Viaggio", "section": "pagine", "hint": "La mappa globale."},
    {"key": "market", "label": "Mercato", "section": "pagine", "hint": "Le botteghe."},
    {"key": "lore", "label": "Lore", "section": "pagine", "hint": "Fazioni, PNG e cronologia."},
    {"key": "media", "label": "Archivio immagini", "section": "pagine", "hint": "La libreria multimediale."},
    {"key": "guide", "label": "Guide", "section": "pagine", "hint": "Le guide di gioco."},
    {"key": "settings", "label": "Impostazioni", "section": "pagine", "hint": "Le preferenze personali."},

    # --- Modali: archivio e impostazioni ------------------------------------
    {"key": "media-preview", "label": "Anteprima immagine", "section": "modali", "hint": "Archivio · apertura di un'immagine."},
    {"key": "media-move", "label": "Sposta immagine", "section": "modali", "hint": "Archivio · cambio di categoria o gruppo."},
    {"key": "media-confirm", "label": "Conferma sull'immagine", "section": "modali", "hint": "Archivio · eliminazione o spostamento."},
    {"key": "settings-restart", "label": "Riavvio necessario", "section": "modali", "hint": "Impostazioni · avviso di riavvio."},
    {"key": "image-picker", "label": "Scegli un'immagine", "section": "modali", "hint": "Il selettore usato da tutta l'app."},
    {"key": "weather", "label": "Tempo atmosferico", "section": "modali", "hint": "Barra rapida · meteo della campagna."},

    # --- Modali: personaggio -------------------------------------------------
    {"key": "character-overview", "label": "Modifica panoramica", "section": "modali", "hint": "Scheda · dati generali."},
    {"key": "character-rest", "label": "Riposa", "section": "modali", "hint": "Scheda · riposo del personaggio."},
    {"key": "effect-preset", "label": "Preset effetto", "section": "modali", "hint": "Scheda · scelta di un effetto pronto."},
    {"key": "item-editor", "label": "Editor oggetto", "section": "modali", "hint": "Scheda · creazione o modifica di un oggetto."},

    # --- Modali: combattimento ----------------------------------------------
    {"key": "combat-map-editor", "label": "Editor della mappa", "section": "modali", "hint": "Combattimento · disegno della mappa."},
    {"key": "combat-map-settings", "label": "Impostazioni della mappa", "section": "modali", "hint": "Combattimento · modifica di una mappa."},
    {"key": "combat-import-fighters", "label": "Importa combattenti", "section": "modali", "hint": "Combattimento · aggiunta di partecipanti."},
    {"key": "combat-manage-characters", "label": "Gestisci personaggi", "section": "modali", "hint": "Combattimento · roster del tavolo."},
    {"key": "combat-import-copy", "label": "Importare una copia?", "section": "modali", "hint": "Combattimento · conferma di importazione."},
    {"key": "combat-map-backups", "label": "Backup della mappa", "section": "modali", "hint": "Combattimento · versioni salvate."},
    {"key": "combat-character-public", "label": "Personaggio in combattimento", "section": "modali", "hint": "Combattimento · scheda vista dai giocatori."},
    {"key": "combat-character-manage", "label": "Personaggio: controlli", "section": "modali", "hint": "Combattimento · scheda vista dal Master."},
    {"key": "combat-map-manager", "label": "Gestione mappe", "section": "modali", "hint": "Combattimento · elenco dei tavoli."},
    {"key": "combat-quick-actions", "label": "Azioni rapide", "section": "modali", "hint": "Combattimento · turno attivo."},

    # --- Modali: guide, lore e mercato --------------------------------------
    {"key": "item-detail", "label": "Dettaglio oggetto", "section": "modali", "hint": "Guide · compendio degli oggetti."},
    {"key": "lore-npc", "label": "Scheda PNG", "section": "modali", "hint": "Lore · apertura di un personaggio."},
    {"key": "lore-faction-editor", "label": "Editor fazione", "section": "modali", "hint": "Lore · creazione o modifica di una fazione."},
    {"key": "lore-npc-editor", "label": "Editor PNG", "section": "modali", "hint": "Lore · creazione o modifica di un PNG."},
    {"key": "lore-reactions", "label": "Matrice delle reazioni", "section": "modali", "hint": "Lore · rapporti fra fazioni."},
    {"key": "lore-faction-history", "label": "Storico della fazione", "section": "modali", "hint": "Lore · cronologia dei rapporti."},
    {"key": "lore-timeline-event", "label": "Evento della Timeline", "section": "modali", "hint": "Lore · cronologia della campagna."},
    {"key": "market-shop-editor", "label": "Editor bottega", "section": "modali", "hint": "Mercato · modifica di un negozio."},

    # --- Modali: abilità -----------------------------------------------------
    {"key": "skills-reminder", "label": "Promemoria abilità", "section": "modali", "hint": "Abilità · nota di un'azione."},
    {"key": "skills-unlock", "label": "Sblocco abilità", "section": "modali", "hint": "Abilità · anteprima di acquisto."},
    {"key": "skills-detail", "label": "Dettaglio abilità", "section": "modali", "hint": "Abilità · scheda completa."},
    {"key": "skills-create", "label": "Crea abilità", "section": "modali", "hint": "Abilità · nuova voce."},
    {"key": "skills-xp", "label": "Modifica Punti Esperienza", "section": "modali", "hint": "Abilità · gestione dei PE."},
    {"key": "skills-progression", "label": "Progressione del personaggio", "section": "modali", "hint": "Abilità · analisi PG."},
    {"key": "skills-stats", "label": "Statistiche delle skill", "section": "modali", "hint": "Abilità · analisi PG."},
    {"key": "skills-effects", "label": "Effetti e azioni dalle skill", "section": "modali", "hint": "Abilità · analisi PG."},
    {"key": "skills-button-editor", "label": "Editor pulsante rapido", "section": "modali", "hint": "Abilità · scorciatoie personalizzate."},

    # --- Modali: viaggio -----------------------------------------------------
    {"key": "travel-marker", "label": "Icona sulla mappa", "section": "modali", "hint": "Viaggio · inserimento di un tag."},

    # --- Strumenti rapidi ----------------------------------------------------
    {"key": "journal", "label": "Diario", "section": "strumenti-rapidi", "hint": "Barra rapida · diario di bordo."},
    {"key": "dice", "label": "Dadi", "section": "strumenti-rapidi", "hint": "Barra rapida · tiri."},
    {"key": "ai", "label": "AI", "section": "strumenti-rapidi", "hint": "Barra rapida · assistente."},
    {"key": "audio", "label": "Audio", "section": "strumenti-rapidi", "hint": "Barra rapida · colonna sonora."},
    {"key": "theft", "label": "Furto", "section": "strumenti-rapidi", "hint": "Barra rapida · scasso e borseggio."},

    # --- Strumenti (Master e amministratori) --------------------------------
    {"key": "tools", "label": "Strumenti", "section": "strumenti", "hint": "Tutte le schermate sotto /tools e le loro finestre."},
]

THEME_SURFACE_KEYS = [entry["key"] for entry in THEME_SURFACES]
THEME_SURFACE_KEY_SET = frozenset(THEME_SURFACE_KEYS)

# Le vecchie colonne di Theme, per la migrazione dei dati esistenti.
# «characters_background» non compare: la rotta /characters rimanda alla Sala
# principale, quindi quello sfondo non era più raggiungibile.
LEGACY_BACKGROUND_COLUMNS = {
    "dashboard_background": "dashboard",
    "personaggio_background": "personaggio",
    "media_background": "media",
    "guide_background": "guide",
    "settings_background": "settings",
    "dice_background": "dice",
    "journal_background": "journal",
    "lore_background": "lore",
    "market_background": "market",
}


def surfaces_in_section(section_key: str) -> list[dict]:
    return [entry for entry in THEME_SURFACES if entry["section"] == section_key]

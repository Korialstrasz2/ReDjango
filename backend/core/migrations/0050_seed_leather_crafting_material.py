from django.db import migrations


# Il livello 1 della forgiatura Elder e' "Ferro, Pelle, Legno", ma il catalogo
# aveva soltanto due dei tre materiali: `Lingotto di ferro` e `Legno per armi`.
# La pelle esisteva solo come tipo_2 di armature gia' finite, quindi la skill
# "Uso pratico 1" ("consuma 2 unita' di pelle") non aveva nulla da consumare.
#
# La riga vive fra i `lingotto` anche se la pelle non e' un lingotto: e' il tipo
# che il Mercato gia' assegna ai materiali da forgiatura (armaiolo e emporio
# generale li vendono con rank 3) ed e' il tipo su cui la Forgiatura leggera'
# le scorte. Peso, rarita' e valore seguono gli altri materiali di livello 1.
LEATHER_NAME = "Pelle conciata"
LEATHER_DEFAULTS = {
    "modello": True,
    "temporaneo": False,
    "archiviato": False,
    "speciale": False,
    "tipo_1": "lingotto",
    "tipo_2": "lingotto",
    "valore": 25,
    "peso": 1.0,
    "rarita": 1,
    "descrizione": (
        "Materiale da lavorazione di livello 1, alternativa leggera a ferro e legno. "
        "Si consuma a unita' nella creazione di faretre, porta pozioni, porta pergamene e mantelli."
    ),
    "metadata": {"seed_kind": "forge_material", "seed_version": "1", "materialKey": "pelle", "materialTier": 1},
}


def seed_leather(apps, schema_editor):
    Oggetto = apps.get_model("core", "Oggetto")
    Oggetto.objects.get_or_create(nome=LEATHER_NAME, defaults=LEATHER_DEFAULTS)


def unseed_leather(apps, schema_editor):
    Oggetto = apps.get_model("core", "Oggetto")
    # Solo la riga creata da questa migrazione: se qualcuno l'ha gia' usata come
    # modello e l'ha modificata a mano, il seed_kind resta la prova che e' nostra.
    Oggetto.objects.filter(
        nome=LEATHER_NAME,
        metadata__seed_kind="forge_material",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0049_drop_item_authoring_stubs"),
    ]

    operations = [
        migrations.RunPython(seed_leather, unseed_leather),
    ]

from django.db import migrations


# alchemy_profile e crafting_profile erano i contenitori ereditati dalla fusione
# di IngredientiAlchimia nel catalogo oggetti: JSON liberi, senza schema, che
# nessuna logica di gioco ha mai letto. Un solo oggetto su 5895 ne aveva uno
# compilato (un seed dimostrativo) e il rischio era che qualcuno ci scrivesse
# dentro regole convinto che il sistema le applicasse. notes seguiva la stessa
# sorte: mai compilato su nessun oggetto. Il crafting, quando arrivera, si
# portera dietro il proprio schema esplicito invece di questi tre buchi neri.
class Migration(migrations.Migration):

    dependencies = [
        ("core", "0048_drop_barrier_accessory_kinds"),
    ]

    operations = [
        migrations.RemoveField(model_name="oggetto", name="alchemy_profile"),
        migrations.RemoveField(model_name="oggetto", name="crafting_profile"),
        migrations.RemoveField(model_name="oggetto", name="notes"),
    ]

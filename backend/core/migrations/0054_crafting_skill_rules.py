from django.db import migrations


# Le abilita' Fabbro e Incantatore portavano la loro regola solo in prosa
# italiana: leggibile al tavolo, invisibile al motore. Questa migrazione la
# riscrive in dati, con la stessa divisione che usa il resto del progetto —
# effetti_passivi per le grandezze (finiscono in Personaggio.tot), metadata per
# i permessi (li legge il servizio, come gia' fa skill_pricing con
# pricingModifier). Le abilita' che il motore non sa rappresentare ottengono un
# table_rule esplicito invece di restare mute.
#
# Idempotente: riscrive solo cio' che genera, e i passivi legacy gia' presenti
# (Moda delle anime, Arte delle anime) restano intatti perche' plan_for non li
# riconosce.
def apply_crafting_rules(apps, schema_editor):
    Skill = apps.get_model("core", "Skill")
    from backend.core.crafting_skill_rules import plan_for

    for skill in Skill.objects.filter(famiglia__nome__in=("Fabbro", "Incantatore")).select_related("famiglia"):
        plan = plan_for(skill.famiglia.nome, skill.nome)
        if plan is None:
            continue
        fields = []
        if plan["passives"]:
            skill.effetti_passivi = plan["passives"]
            fields.append("effetti_passivi")
        metadata = dict(skill.metadata) if isinstance(skill.metadata, dict) else {}
        metadata[plan["key"]] = plan["rule"]
        skill.metadata = metadata
        fields.append("metadata")
        skill.save(update_fields=[*fields, "updated_at"])


def clear_crafting_rules(apps, schema_editor):
    Skill = apps.get_model("core", "Skill")
    from backend.core.crafting_skill_rules import ENCHANT_RULE_KEY, FORGE_RULE_KEY, plan_for

    for skill in Skill.objects.filter(famiglia__nome__in=("Fabbro", "Incantatore")).select_related("famiglia"):
        plan = plan_for(skill.famiglia.nome, skill.nome)
        if plan is None:
            continue
        metadata = dict(skill.metadata) if isinstance(skill.metadata, dict) else {}
        metadata.pop(FORGE_RULE_KEY, None)
        metadata.pop(ENCHANT_RULE_KEY, None)
        skill.metadata = metadata
        fields = ["metadata"]
        if plan["passives"]:
            skill.effetti_passivi = []
            fields.append("effetti_passivi")
        skill.save(update_fields=[*fields, "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0053_market_assortment_dials"),
    ]

    operations = [
        migrations.RunPython(apply_crafting_rules, clear_crafting_rules),
    ]

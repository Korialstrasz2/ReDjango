from decimal import Decimal, InvalidOperation

from django.db import migrations


# A spell now owns its whole cost model: base_mana is the fixed part, effect_per_mana
# the variable part and fixed_costs the non-mana extras. The legacy import also wrote
# the fixed mana onto the skill's active reminder, so the same Mana was charged twice
# once the modal started adding the reminder costs. Move each reminder cost into the
# spell definition and clear it from the reminder.
FIXED_RESOURCES = ("pf", "energia", "potere", "pa", "stanchezza")


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def merge_action_costs_into_spell(apps, schema_editor):
    SpellDefinition = apps.get_model("core", "SpellDefinition")
    for definition in SpellDefinition.objects.select_related("skill"):
        skill = definition.skill
        actions = skill.azioni_attive if isinstance(skill.azioni_attive, list) else []
        fixed_costs = dict(definition.fixed_costs) if isinstance(definition.fixed_costs, dict) else {}
        extra_mana = Decimal("0")
        rewritten = []
        changed = False
        for action in actions:
            costs = action.get("costs") if isinstance(action, dict) else None
            if not isinstance(costs, dict) or not any(costs.values()):
                rewritten.append(action)
                continue
            mana = _decimal(costs.get("mana") or 0) or Decimal("0")
            # The importer copied the spell's own fixed Mana onto the reminder; only
            # an amount the formula does not already charge is a genuine extra.
            if mana and mana != definition.base_mana and not (
                definition.base_mana == 0 and mana == definition.minimum_mana
            ):
                extra_mana += mana
            for resource in FIXED_RESOURCES:
                amount = _decimal(costs.get(resource) or 0) or Decimal("0")
                if amount:
                    fixed_costs[resource] = max(_decimal(fixed_costs.get(resource) or 0) or Decimal("0"), amount)
            rewritten.append({**action, "costs": {}})
            changed = True
        if not changed:
            continue
        skill.azioni_attive = rewritten
        skill.save(update_fields=["azioni_attive", "updated_at"])
        definition.base_mana = definition.base_mana + extra_mana
        definition.fixed_costs = {key: float(value) for key, value in fixed_costs.items() if value}
        definition.save(update_fields=["base_mana", "fixed_costs", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0037_spelldefinition_fixed_costs"),
    ]

    operations = [
        migrations.RunPython(merge_action_costs_into_spell, migrations.RunPython.noop),
    ]

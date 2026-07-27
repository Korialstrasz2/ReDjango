import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase

from backend.core.defaults import V2_SETTING_DEFAULTS
from backend.core.models import Negozio, SettingDefinition
from backend.market.shop_plan import load_plan, validate_plan


class ShopPlanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for definition in V2_SETTING_DEFAULTS:
            if definition["key"].startswith("mercato."):
                SettingDefinition.objects.create(**definition, value=definition["default_value"])

    def record(self, **overrides):
        value = {
            "planId": 1, "locationKey": "skyrim/whiterun", "categoryKey": "armaiolo", "level": 2,
            "name": "Forgia della Porta Nord", "owner": "Hjorn Fabbri", "description": "Una bottega stretta presso la porta nord, nota per riparazioni pazienti e ferri affidabili per carovane che arrivano prima dell'alba.",
            "seed": "elder-plan-0001", "status": "approved",
        }
        value.update(overrides)
        return value

    def test_clean_record_is_planned_for_creation(self):
        report = validate_plan([self.record()])
        self.assertFalse(report.errors, report.payload())
        self.assertEqual(report.payload()["created"], 1)

    def test_same_existing_record_is_skipped_but_different_one_conflicts(self):
        record = self.record()
        Negozio.objects.create(nome=record["name"], proprietario=record["owner"], categoria=record["categoryKey"], livello=record["level"], descrizione=record["description"], location_key=record["locationKey"])
        self.assertEqual(validate_plan([record]).payload()["skipped"], 1)
        self.assertTrue(validate_plan([self.record(description="Una descrizione diversa con abbastanza parole per superare deliberatamente il controllo obbligatorio richiesto dal piano approvato qui.")]).errors)

    def test_needs_review_records_are_not_import_candidates(self):
        report = validate_plan([self.record(status="needs_review")])
        self.assertFalse(report.errors)
        self.assertEqual(report.payload()["created"], 0)

    def test_load_plan_accepts_records_envelope(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps({"records": [self.record()]}), encoding="utf-8")
            self.assertEqual(load_plan(path)[0]["planId"], 1)

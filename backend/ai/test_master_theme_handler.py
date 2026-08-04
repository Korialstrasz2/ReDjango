from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.core.api import ApiError
from backend.core.models import Giocatore, Theme

from .changes.services import add_change_operation, apply_change_set, create_change_set, validate_change_set


class MasterAIThemeHandlerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_user(username="master_ai_theme_admin")
        cls.admin = Giocatore.objects.create(
            user=cls.admin_user,
            nome="master_ai_theme_admin",
            role=Giocatore.ROLE_ADMIN,
        )

    def test_admin_can_create_theme_through_human_apply(self):
        change_set = create_change_set(self.admin_user, self.admin, title="Tema")
        add_change_operation(
            self.admin_user,
            self.admin,
            change_set.id,
            entity_type="theme",
            action="create",
            values={"name": "Tema proposto", "description": "Creato dalla proposta"},
        )
        ready = validate_change_set(self.admin_user, self.admin, change_set.id)
        apply_change_set(self.admin_user, self.admin, change_set.id, ready.validation_token)
        theme = Theme.objects.get(name="Tema proposto")
        self.assertTrue(theme.is_active)
        self.assertFalse(theme.is_default)

    def test_default_theme_cannot_be_deactivated_during_dry_validation(self):
        theme = Theme.objects.create(name="Default", slug="default-proposal-test", is_default=True, is_active=True)
        change_set = create_change_set(self.admin_user, self.admin, title="Default")
        with self.assertRaises(ApiError) as captured:
            add_change_operation(
                self.admin_user,
                self.admin,
                change_set.id,
                entity_type="theme",
                action="update",
                target_id=theme.id,
                values={"isActive": False},
            )
        self.assertEqual(captured.exception.code, "management.themes.default_must_stay_active")
        theme.refresh_from_db()
        self.assertTrue(theme.is_active)

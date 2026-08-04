from django.contrib.auth import get_user_model
from django.test import TestCase

from backend.ai.change_views import _clear_ready_validation
from backend.ai.models import AIChangeSet


class MasterAIStaleInvalidationTests(TestCase):
    def test_stale_apply_conflict_returns_ready_set_to_draft(self):
        user = get_user_model().objects.create_user(username="master_ai_stale")
        change_set = AIChangeSet.objects.create(
            user=user,
            status=AIChangeSet.STATUS_READY,
            validation_token="signed-ready-token",
            validation_summary={"selectedCount": 1, "errorCount": 0},
        )

        _clear_ready_validation(user, change_set.id)

        change_set.refresh_from_db()
        self.assertEqual(change_set.status, AIChangeSet.STATUS_DRAFT)
        self.assertEqual(change_set.validation_token, "")
        self.assertEqual(change_set.validation_summary, {})
        self.assertIsNone(change_set.validated_at)

    def test_other_users_cannot_invalidate_the_proposal(self):
        owner = get_user_model().objects.create_user(username="master_ai_owner")
        stranger = get_user_model().objects.create_user(username="master_ai_stranger")
        change_set = AIChangeSet.objects.create(
            user=owner,
            status=AIChangeSet.STATUS_READY,
            validation_token="owner-token",
        )

        _clear_ready_validation(stranger, change_set.id)

        change_set.refresh_from_db()
        self.assertEqual(change_set.status, AIChangeSet.STATUS_READY)
        self.assertEqual(change_set.validation_token, "owner-token")

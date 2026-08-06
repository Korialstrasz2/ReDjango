from django.test import SimpleTestCase

from backend.core.campaigns import _visible_special_resource_proposals


class VisibleSpecialResourceProposalsTests(SimpleTestCase):
    @staticmethod
    def proposal(identifier: str, status: str, actor_id: int, created_at: str) -> dict:
        return {
            "id": identifier,
            "status": status,
            "createdAt": created_at,
            "proposedBy": {"id": actor_id, "name": f"Player {actor_id}"},
        }

    def test_pending_requests_are_not_evicted_by_reviewed_history(self):
        proposals = [
            self.proposal(f"reviewed-{index}", "approved", 2, f"2026-08-06T12:{index:02d}:00Z")
            for index in range(60)
        ]
        proposals.append(self.proposal("old-pending", "pending", 3, "2026-08-01T10:00:00Z"))

        visible = _visible_special_resource_proposals(proposals, giocatore_id=1, can_manage=True)

        self.assertEqual(visible[0]["id"], "old-pending")
        self.assertIn("old-pending", {proposal["id"] for proposal in visible})
        self.assertEqual(len(visible), 50)

    def test_player_only_receives_their_own_requests(self):
        proposals = [
            self.proposal("mine-pending", "pending", 2, "2026-08-06T12:00:00Z"),
            self.proposal("other-pending", "pending", 3, "2026-08-06T13:00:00Z"),
            self.proposal("mine-reviewed", "rejected", 2, "2026-08-06T14:00:00Z"),
        ]

        visible = _visible_special_resource_proposals(proposals, giocatore_id=2, can_manage=False)

        self.assertEqual(
            [proposal["id"] for proposal in visible],
            ["mine-pending", "mine-reviewed"],
        )

    def test_more_than_fifty_pending_requests_remain_visible(self):
        proposals = [
            self.proposal(f"pending-{index}", "pending", 2, f"2026-08-06T12:{index:02d}:00Z")
            for index in range(55)
        ]

        visible = _visible_special_resource_proposals(proposals, giocatore_id=1, can_manage=True)

        self.assertEqual(len(visible), 55)
        self.assertTrue(all(proposal["status"] == "pending" for proposal in visible))

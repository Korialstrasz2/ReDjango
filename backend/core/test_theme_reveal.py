from types import SimpleNamespace

from django.test import SimpleTestCase

from .api import ApiError
from .theme_reveal import apply_reveal_payload, reveal_values


class ThemeRevealTests(SimpleTestCase):
    def test_defaults_are_half_second_hold_and_one_second_fade(self):
        theme = SimpleNamespace(metadata={})

        self.assertEqual(reveal_values(theme), {
            "revealHoldSeconds": 0.5,
            "revealFadeSeconds": 1.0,
        })

    def test_payload_is_persisted_in_theme_metadata(self):
        theme = SimpleNamespace(metadata={"other": True})

        apply_reveal_payload(theme, {
            "revealHoldSeconds": 0.8,
            "revealFadeSeconds": 1.4,
        })

        self.assertEqual(theme.metadata, {
            "other": True,
            "background_reveal_hold_seconds": 0.8,
            "background_reveal_fade_seconds": 1.4,
        })
        self.assertEqual(reveal_values(theme), {
            "revealHoldSeconds": 0.8,
            "revealFadeSeconds": 1.4,
        })

    def test_duration_outside_supported_range_is_rejected(self):
        theme = SimpleNamespace(metadata={})

        with self.assertRaises(ApiError):
            apply_reveal_payload(theme, {"revealHoldSeconds": 5.1})

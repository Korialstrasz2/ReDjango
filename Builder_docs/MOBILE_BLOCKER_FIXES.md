# Mobile blocker corrections

This document records the corrections made on `mobile-optimized` after the desktop-preservation review.

## Shared modal behavior

- Desktop dialogs retain the original default: backdrop clicks close the dialog unless `closeOnBackdrop={false}` is supplied explicitly.
- Phone sheet and full-screen presentations may infer a stricter default for wide, resizable, headless, or body-draggable editors.
- Unit coverage verifies desktop defaults, explicit opt-out, and phone behavior.

## Desktop verification

- The CI workflow runs the complete canonical `authenticated` Playwright project separately from the responsive matrix.
- A protected visual job compares the pinned desktop baseline commit `da846aca31d31b15e4128f70b0cf0e6cb3b32283` with the candidate branch at 1280×800, 1440×900, and 1920×1080.
- Baseline images are regenerated from the pinned commit during CI. Candidate differences fail instead of updating snapshots.

## Phone management routes

- Permission checks remain unchanged.
- Authorized phone users receive an intentional limitation route element.
- Management pages are not mounted beneath the limitation screen.
- The requested URL remains in place, with explicit Back and Home actions.

## Combat and Travel mobile workspaces

- Both workspaces expose a shared explicit route-level Back bar.
- Back closes the top modal or child surface first, returns to the primary map panel, then uses router history with a Home fallback for direct entry.
- Hardware Escape follows the same order when no modal owns Escape.
- Travel cancels pending marker placement before route navigation.
- Combat preserves an attack sequence while returning to the map and requests confirmation before route navigation would discard unapplied local attack state.

## Scope

All behavior and styling introduced by these corrections is phone-scoped or explicitly restores the desktop contract. No change is applied to the desktop navigation hierarchy, modal dimensions, dragging, resizing, or route structure.

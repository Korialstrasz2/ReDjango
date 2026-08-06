# Combat Confirmation Modal Checkpoint

Branch: `mobile-optimized`

Implementation under verification: `a1cdafa394a6a7bf52e907e7678f7f541caafd58`

This checkpoint replaces the remaining native Combat confirmation prompts with the shared modal stack:

- duplicate planned-action confirmation;
- clear unpaid action queue confirmation;
- restore map snapshot confirmation.

The implementation preserves the existing mutation payloads and command paths. Confirmation dialogs keep the parent planner or backup workspace mounted and inert, support Escape cancellation and focus restoration, and require explicit confirmation for destructive actions.

Verification includes a real desktop-master workflow covering cancellation and confirmation for duplicate planning, queue clearing, and snapshot restore. Status remains pending until frontend validation and the expanded responsive Playwright matrix pass.

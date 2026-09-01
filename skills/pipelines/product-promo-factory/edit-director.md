# Edit Director

Edit to the approved timing contract. Keep the hook module, body module, proof module,
and CTA separable so `campaign_batch` can assemble controlled variants. Captions must
remain inside platform safe zones and emphasize the user's words, not every word.

Export an editable timeline. Do not center-crop a landscape master into vertical;
use profile-specific reflow sources. When testing variants, change only the dimensions
declared by `campaign_plan.experiment`.

Copy the approved `render_runtime` and composition mode from `proposal_packet` into
`edit_decisions`. Editing must not change either choice. If the planned runtime can
no longer satisfy the proof or format requirements, surface the blocker and append
an approved decision revision before rebuilding the timeline.

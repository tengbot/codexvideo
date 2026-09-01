# Continuity Director

Turn the approved proof and scene plans into a `visual_continuity_bible`. Lock
the real product identity, first-party surfaces, palette, typography, lighting,
camera behavior, motion rules, and forbidden substitutions before assets are
generated or composed.

Every scene must inherit named continuity locks and declare what visual state it
receives from the previous scene and hands to the next. Generated imagery may
support a scene, but it cannot impersonate a product screen, price, model name,
result, testimonial, or other first-party proof.

Hash every upstream artifact that changes visual decisions. Record which
downstream artifacts become stale when that hash changes. This contract
independently adapts OpenStory's story-bible and dependency-invalidation ideas;
it does not add OpenStory as a runtime service or require its model providers.
Record the audited upstream commit and MIT license in the artifact.

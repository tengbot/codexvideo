"""Contracts for the faceless and synthetic-dialogue content formats."""

from pathlib import Path

from lib.pipeline_loader import get_stage_order, list_pipelines, load_pipeline
from schemas.artifacts import ARTIFACT_NAMES, validate_artifact


ROOT = Path(__file__).resolve().parent.parent.parent
EXPECTED_STAGES = [
    "research",
    "proposal",
    "script",
    "scene_plan",
    "assets",
    "edit",
    "compose",
    "publish",
]


def test_content_format_pipelines_are_listed_and_complete():
    available = set(list_pipelines())
    assert {"faceless-narrative", "ai-dialogue-podcast"}.issubset(available)

    for name in ("faceless-narrative", "ai-dialogue-podcast"):
        manifest = load_pipeline(name)
        assert get_stage_order(manifest) == EXPECTED_STAGES
        for skill_ref in manifest["required_skills"]:
            assert (ROOT / "skills" / f"{skill_ref}.md").is_file(), skill_ref


def test_content_format_artifacts_are_registered():
    assert {
        "hook_candidates",
        "visual_match",
        "dialogue_script",
        "cast_bible",
        "audio_timeline",
    }.issubset(set(ARTIFACT_NAMES))


def test_hook_candidates_schema_accepts_scored_need_driven_hooks():
    validate_artifact(
        "hook_candidates",
        {
            "version": "1.0",
            "topic": "Choosing a random video chat service",
            "audience": "Adults who want a fast conversation without hidden friction",
            "candidates": [
                {
                    "id": f"hook-{index}",
                    "text": text,
                    "human_need": "Avoid wasting time on the wrong service",
                    "promise": "A practical decision rule",
                    "format_fits": ["faceless_narrative", "ai_dialogue_podcast"],
                    "scores": {"truth": 5, "retention": 4, "relevance": 5, "total": 14},
                    "evidence_refs": ["source-home"],
                }
                for index, text in enumerate(
                    [
                        "The fastest video chat app may be the wrong one for you.",
                        "Before you open a random chat site, check these three things.",
                        "Free video chat often starts with a hidden tradeoff.",
                    ],
                    start=1,
                )
            ],
            "selected_id": "hook-2",
            "approval": {"status": "approved", "notes": "Consumer-first and specific"},
        },
    )


def test_dialogue_and_cast_schemas_accept_two_stable_hosts():
    validate_artifact(
        "dialogue_script",
        {
            "version": "1.0",
            "title": "Pick the right video chat",
            "language": "en-US",
            "duration_target_seconds": 30,
            "hook": "Is the fastest random chat site actually the safest choice?",
            "host_ids": ["host-a", "host-b"],
            "turns": [
                {"id": "t1", "speaker_id": "host-a", "line": "Is faster always better?", "intent": "hook", "emotion": "curious", "duration_seconds": 2.2, "shot": "host_a_closeup"},
                {"id": "t2", "speaker_id": "host-b", "line": "Only if you ignore signup and safety friction.", "intent": "answer", "emotion": "measured", "duration_seconds": 3.0, "shot": "host_b_closeup"},
                {"id": "t3", "speaker_id": "host-a", "line": "So what should I check first?", "intent": "question", "emotion": "engaged", "duration_seconds": 2.4, "shot": "host_a_closeup"},
                {"id": "t4", "speaker_id": "host-b", "line": "Match the service to the conversation you actually want.", "intent": "reveal", "emotion": "confident", "duration_seconds": 3.4, "shot": "evidence_card", "visual_insert": "VideoChat.im goal selector"},
            ],
            "cta": "Compare before you connect.",
        },
    )

    validate_artifact(
        "cast_bible",
        {
            "version": "1.0",
            "format": "ai_dialogue_podcast",
            "studio": {
                "description": "Warm editorial podcast desk with two cameras",
                "palette": ["#101418", "#30d5c8"],
                "continuity_rules": ["Keep eyelines across the desk", "Keep wardrobe unchanged"],
            },
            "hosts": [
                {"id": "host-a", "name": "Maya", "role": "viewer advocate", "personality": ["curious", "direct"], "voice": {"provider": "heygen", "voice_id": "voice-a", "direction": "bright natural American English"}, "avatar": {"provider": "heygen", "avatar_id": "avatar-a", "reference_path": "assets/hosts/maya.png"}, "framing": "camera left medium close-up"},
                {"id": "host-b", "name": "Ethan", "role": "practical guide", "personality": ["calm", "specific"], "voice": {"provider": "heygen", "voice_id": "voice-b", "direction": "warm measured American English"}, "avatar": {"provider": "heygen", "avatar_id": "avatar-b", "reference_path": "assets/hosts/ethan.png"}, "framing": "camera right medium close-up"},
            ],
        },
    )


def test_visual_match_and_audio_timeline_validate():
    validate_artifact(
        "visual_match",
        {
            "version": "1.0",
            "format": "faceless_narrative",
            "scenes": [
                {
                    "scene_id": "s1",
                    "beat_ref": "hook",
                    "visual_intent": "Show indecision before opening a stranger chat service",
                    "candidates": [
                        {
                            "id": "c1",
                            "type": "motion_graphics",
                            "provider": "hyperframes",
                            "source": "designed locally",
                            "source_url": None,
                            "local_path": "assets/video/hook.mp4",
                            "license": "project-owned",
                            "scores": {"relevance": 5, "composition": 5, "motion": 4, "brand_fit": 5, "total": 19},
                        }
                    ],
                    "selected_candidate_id": "c1",
                }
            ],
        },
    )

    validate_artifact(
        "audio_timeline",
        {
            "version": "1.0",
            "duration_seconds": 3.2,
            "segments": [
                {"id": "a1", "kind": "narration", "speaker_id": "narrator", "start_seconds": 0, "end_seconds": 3.2, "source_path": "assets/audio/hook.wav", "transcript": "Before you open a random chat site, check this.", "word_timings_path": "assets/audio/hook.words.json"}
            ],
        },
    )


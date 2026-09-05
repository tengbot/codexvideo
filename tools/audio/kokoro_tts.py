"""Optional cached Kokoro narration with a bounded CPU session; never downloads."""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
from pathlib import Path

from tools.base_tool import BaseTool, ToolResult, ToolRuntime, ToolStatus, ToolTier, ResourceProfile


class KokoroTTS(BaseTool):
    name = "kokoro_tts"
    version = "1.0.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "kokoro"
    runtime = ToolRuntime.LOCAL
    best_for = ["Offline English narration using existing model files"]
    not_good_for = ["Voice cloning", "Automatic model installation", "Word-level alignment"]
    related_skills = ["skills/core/cached-narration.md"]
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=1024, disk_mb=100, network_required=False)
    input_schema = {
        "type": "object", "required": ["text", "output_path"],
        "properties": {
            "text": {"type": "string", "minLength": 1, "maxLength": 2000},
            "output_path": {"type": "string"},
            "model_path": {"type": "string"}, "voices_path": {"type": "string"},
            "voice": {"type": "string", "default": "af_heart"},
            "speed": {"type": "number", "minimum": 0.8, "maximum": 1.3},
        },
    }
    output_schema = {"type": "object"}

    @staticmethod
    def _paths(inputs):
        cache = Path.home() / ".cache/hyperframes/tts"
        return (Path(inputs.get("model_path") or cache / "models/kokoro-v1.0.onnx").expanduser(),
                Path(inputs.get("voices_path") or cache / "voices/voices-v1.0.bin").expanduser())

    def get_status(self):
        installed = all(importlib.util.find_spec(m) for m in ("kokoro_onnx", "onnxruntime", "soundfile"))
        return ToolStatus.AVAILABLE if installed and all(p.is_file() for p in self._paths({})) else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs):
        return 0.0

    def execute(self, inputs):
        model, voices = self._paths(inputs)
        if not model.is_file() or not voices.is_file():
            return ToolResult(success=False, error="Cached Kokoro model/voices missing; no download attempted")
        try:
            import onnxruntime as ort
            import soundfile as sf
            from kokoro_onnx import Kokoro
            from kokoro_onnx.config import EspeakConfig
            import espeakng_loader

            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            session = ort.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"])
            # Some eSpeak builds silently reject long checkout paths and exit the process.
            with tempfile.TemporaryDirectory(prefix="cv-espeak-") as short_dir:
                data = Path(short_dir) / "espeak-ng-data"
                shutil.copytree(espeakng_loader.get_data_path(), data)
                engine = Kokoro.from_session(session, str(voices), EspeakConfig(data_path=str(data)))
                audio, rate = engine.create(inputs["text"], voice=inputs.get("voice", "af_heart"),
                                            speed=float(inputs.get("speed", 1)), lang="en-us")
            output = Path(inputs["output_path"]).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            sf.write(output, audio, rate)
            return ToolResult(success=True, data={"audio_path": str(output), "duration_seconds": len(audio) / rate,
                              "sample_rate": rate, "voice": inputs.get("voice", "af_heart"), "cpu_threads": 1,
                              "timing_source": "measured_audio_duration", "word_timings": None}, artifacts=[str(output)])
        except Exception as exc:
            return ToolResult(success=False, error=f"Cached Kokoro synthesis failed: {exc}")

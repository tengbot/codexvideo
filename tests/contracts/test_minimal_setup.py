import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_default_setup_does_not_install_models_or_renderers():
    result = subprocess.run(["make", "-n", "setup"], cwd=ROOT, capture_output=True, text=True, check=True)
    commands = result.stdout
    assert "install -r requirements-core.txt" in commands
    assert "npm ci" not in commands and "npx --yes" not in commands
    assert "install piper-tts" not in commands
    assert "install -r requirements.txt" not in commands


def test_provider_sdks_are_not_mandatory_package_dependencies():
    tree = ast.parse((ROOT / "setup.py").read_text())
    call = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setup")
    dependencies = ast.literal_eval(next(k.value for k in call.keywords if k.arg == "install_requires"))
    assert not any(d.startswith(("openai", "google", "fastapi", "uvicorn", "faster-whisper")) for d in dependencies)


def test_catalog_and_discovery_work_without_optional_sdk_imports():
    result = subprocess.run([sys.executable, "-c", '''
import importlib.abc
import sys
class NoOptionalSDK(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'openai', 'google', 'fastapi', 'faster_whisper', 'torch'}:
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, NoOptionalSDK())
from codexvideo.catalog import load_catalog
from lib.pipeline_loader import load_pipeline_readonly
from tools.tool_registry import registry
assert 'faceless' in load_catalog()['formats']
assert load_pipeline_readonly('faceless-narrative')['name'] == 'faceless-narrative'
registry.discover()
assert registry.get('creative_qa') is not None
'''], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr

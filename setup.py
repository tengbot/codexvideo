from setuptools import setup, find_packages

setup(
    name="codexvideo",
    version="0.2.0",
    description="Consumer-led, Codex-native video production system",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pyyaml>=6.0",
        "pydantic>=2.0",
        "jsonschema>=4.20",
        "python-dotenv>=1.0",
        "Pillow>=10.0",
        "numpy>=1.24",
        "requests>=2.31",
        "google-genai>=1.0.0",
        "openai>=2.44.0",
    ],
    extras_require={
        "stt": ["faster-whisper>=1.2,<2"],
    },
    entry_points={
        "console_scripts": [
            "codexvideo=codexvideo.cli:main",
        ],
    },
)

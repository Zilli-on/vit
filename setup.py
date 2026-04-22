from setuptools import setup, find_packages

setup(
    name="vit",
    version="0.1.1",
    description="Git for Video Editing — version control timeline metadata, not media files",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "resolve_plugin": ["*.py"],
        "resolve_plugin.graph_assets": ["*.svg"],
    },
    python_requires=">=3.8",
    install_requires=[
        "rich",
    ],
    extras_require={
        "qt": ["PySide6"],
        "gemini": ["google-generativeai"],
        "all": ["PySide6", "google-generativeai"],
    },
    entry_points={
        "console_scripts": [
            "vit=vit.cli:main",
        ],
    },
)

from setuptools import find_namespace_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="devo-cli",
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    packages=find_namespace_packages(include=["cli_tool*"]),
    include_package_data=True,
    author="Eduardo De la Cruz",
    author_email="edudelacruzrojas@gmail.com",
    description="A CLI tool for developers with AI-powered features.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/edu526/devo-cli",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.12",
    install_requires=[
        "click==8.1.8",
        "jinja2==3.1.6",
        "requests==2.32.3",
        "rich>=13.0.0",
        "tzdata>=2025.2",
        "strands-agents>=1.7.0",
        "gitpython>=3.1.0",
    ],
    entry_points={
        "console_scripts": [
            "devo=cli_tool.cli:main",
        ],
    },
    package_data={
        "cli_tool": ["templates/*.j2", "commands/*.py", "utils/*.py", "config.py"],
    },
)

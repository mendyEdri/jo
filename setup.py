from setuptools import setup, find_packages

setup(
    name="jo",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.1.0",
    ],
    entry_points={
        'console_scripts': [
            'jo=git_analyzer.cli:cli',
        ],
    },
    python_requires='>=3.8',
)

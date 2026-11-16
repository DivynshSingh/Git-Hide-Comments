from setuptools import setup, find_packages

setup(
    name="git-hc",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "pygments>=2.14.0",
    ],
    scripts=["git-hc"],
    entry_points={
        "console_scripts": [
            "git-hc = hc.cli:main",
        ],
    },
)

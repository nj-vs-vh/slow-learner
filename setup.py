from setuptools import find_packages, setup

setup(
    name="slow-learner",
    version="0.0.1",
    author="Igor Vaiman",
    description="Learning Python type hints from a stream of data",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=["click~=8.1", "tqdm>=4.0.0"],
    entry_points={
        "console_scripts": ["slow-learner=slow_learner.cli:cli"],
    },
)

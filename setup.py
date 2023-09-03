import os

from setuptools import find_packages, setup

os.environ["SETUPTOOLS_USE_DISTUTILS"] = "stdlib"


setup(
    name="pvValidatorUtils",
    packages=find_packages(),
    package_data={"": ["*.so*"]},
    version="1.7.0",
    description="pvValidator Utils Python Wrapper",
    author="Alfio Rizzo",
    author_email="alfio.rizzo@ess.eu",
    license="GPL",
    zip_safe=False,
    platforms=["Linux", "WSL"],
    scripts=["bin/pvValidator.py"],
    dependency_links=[
        "https://artifactory.esss.lu.se/artifactory/ics-pypi/run-iocsh/0.8.0/run-iocsh-0.8.0.tar.gz"
    ],
    install_requires=["requests", "pytest", "run-iocsh"],
    tests_require=["pytest"],
)

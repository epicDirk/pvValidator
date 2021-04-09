from setuptools import find_packages, setup

setup(
    name="pvValidatorUtils",
    packages=find_packages(),
    package_data={"": ["*.so"]},
    version="1.3.0",
    description="pvValidator Utils Python Wrapper",
    author="Alfio Rizzo",
    author_email="alfio.rizzo@ess.eu",
    license="GPL",
    zip_safe=False,
    platforms=["Linux", "WSL"],
    scripts=["bin/pvValidator.py"],
    install_requires=["requests"],
)

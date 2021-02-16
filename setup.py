from setuptools import setup, find_packages


setup(
    name="pvValidatorUtils",
    packages=find_packages(),
    package_data={"": ["*.so"]},
    version="1.0.0",
    description="pvValidator Utils Python Wrapper",
    author="Alfio Rizzo",
    author_email="alfio.rizzo@ess.eu",
    license="GPL",
    platforms=["Linux", "WSL"],
    scripts=["bin/pvValidator.py"],
    install_requires=["requests"],
)

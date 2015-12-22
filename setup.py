"""
Setup file for automat
"""

from setuptools import setup, find_packages

setup(
    name='Automat',
    version='0.3.0',
    description="""
    Self-service finite-state machines for the programmer on the go.
    """,
    packages=find_packages(exclude=[]),
    package_dir={'automat': 'automat'},
    install_requires=[
        "characteristic",
        "six",
    ],
    include_package_data=True,
    license="MIT",
)

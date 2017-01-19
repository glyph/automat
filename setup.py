"""
Setup file for automat
"""

from setuptools import setup, find_packages

setup(
    name='Automat',
    use_scm_version=True,
    description="""
    Self-service finite-state machines for the programmer on the go.
    """.strip(),
    packages=find_packages(exclude=[]),
    package_dir={'automat': 'automat'},
    setup_requires=[
        'setuptools-scm',
    ],
    install_requires=[
        "attrs",
        "six",
    ],
    extras_require={
        "visualize": ["graphviz>0.5.1",
                      "Twisted>=16.1.1"],
    },
    entry_points={
        "console_scripts": [
            "automat-visualize = automat._visualize:tool"
        ],
    },
    author_name='Glyph',
    author_mail='glyph@twistedmatrix.com',
    include_package_data=True,
    license="MIT",
)

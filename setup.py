"""
Setup file for automat
"""

from setuptools import setup, find_packages

setup(
    name='Automat',
    use_scm_version=True,
    url='https://github.com/glyph/Automat',
    description="""
    Self-service finite-state machines for the programmer on the go.
    """.strip(),
    readme='README.md',
    packages=find_packages(exclude=[]),
    package_dir={'automat': 'automat'},
    setup_requires=[
        'wheel',
        'setuptools-scm',
    ],
    install_requires=[
        "attrs>=19.2.0",
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
    author='Glyph',
    author_email='glyph@twistedmatrix.com',
    include_package_data=True,
    license="MIT",
    keywords='fsm finite state machine automata',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
)

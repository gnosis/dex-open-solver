import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dex-open-solver_gnosis",
    version="0.1.0",
    author="Gnosis Team",
    author_email="marco.correia@gnosis.io",
    description="Batch auction solver for Gnosis Protocol.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gnosis/dex-open-solver",
    packages=[
        'dex_open_solver',
        'dex_open_solver.core',
        'dex_open_solver.best_token_pair_solver',
        'dex_open_solver.token_pair_solver'
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6.9',
    install_requires=[
        "networkx==2.4"
    ],
    extras_require={
        "dev": [
            "pytest==5.3.2",
            "flake8==3.7.9",
            "hypothesis==5.6.0",
            "attrs >=19.3.0"
        ]
    },
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    entry_points={
        "console_scripts": [
            "gp_match = dex_open_solver.match:main"
        ]
    }
)

#!/usr/bin/env python

from setuptools import setup

with open("README.rst", "r") as f:
    long_description = f.read()

with open("requirements.txt", "r") as f:
    requirements = [l.strip() for l in f if l.strip()]

setup(
    name="igstools",
    version="0.9",
    description="Tools for parsing bluray IGS menus",
    long_description=long_description,
    author="Joe Hu (SAPikachu)",
    author_email="i@sapika.ch",
    url="https://github.com/SAPikachu/igstools",
    packages=["igstools"],
    install_requires=requirements,
    entry_points={
        "console_scripts": ["igs_to_png = igstools.__main__:main"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.3",
        "Topic :: Multimedia :: Video",
    ],
)

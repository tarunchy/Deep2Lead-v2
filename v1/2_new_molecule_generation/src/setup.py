import os
from setuptools import find_packages, setup

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='processor',
    version='1.0.0',
    packages=find_packages(),
    include_package_data=True,
    url='',
    classifiers=[
        'Programming Language :: Python :: 3',
    ],
    install_requires=['keras<=2.0.7'],
)

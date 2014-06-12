#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name="ExternalNaginator",
    version="0.0.1",
    packages=find_packages(),
    include_package_data=True,
    author="Daniel Lawrence",
    author_email="dannyla@linux.com",
    description="Generate nagios configuration from puppetdb",
    scripts=["generate.py"],
    license="MIT",
    keywords="puppetdb nagios",
    url="http://github.com/daniellawrence/external_naginator",
)

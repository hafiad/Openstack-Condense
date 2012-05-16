#!/usr/bin/python
# vi: ts=4 expandtab
#
#    Distutils magic for ec2-init
#    Copyright (C) 2009 Canonical Ltd.
#
#    Author: Soren Hansen <soren@canonical.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License version 3, as
#    published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
from glob import glob

from setuptools import (setup, find_packages)

FINAL = False
VERSION = ['2012', '5', '16']


def version_string():
    vstr = '.'.join(VERSION)
    if FINAL:
        return vstr
    else:
        return "%s-dev" % (vstr)


def parse_requires(fn='requires.txt'):
    requires = []
    with open(fn, 'r') as fh:
        lines = fh.read().splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        else:
            requires.append(line)
    return requires


def get_scripts():
    scripts = ['bin/condenser']
    return scripts


def get_data_files():
    data_files = []
    data_files.append(('/etc/condense', glob('config/*.cfg')))
    data_files.append(('/etc/condense/templates', glob('templates/*')))
    data_files.append(('/etc/init', glob('upstart/*.conf')))
    return data_files


setup(name='condense',
      version=version_string(),
      description='Condensed EC2 initialization hot sauce magic!',
      author='Yahoo!',
      author_email='openstack-dev@yahoo-inc.com',
      packages=find_packages(),
      scripts=get_scripts(),
      install_requires=parse_requires(),
      data_files=get_data_files(),
      )

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


def parse_requires(fn='requires.txt'):
    requires = []
    with open(fn, 'r') as fh:
        lines = fh.read().splitlines()
    for line in lines:
        line = line.strip()
        if not line or line[0] == '#':
            continue
        else:
            requires.append(line)
    return requires


def get_version(fn='version.txt'):
    with open(fn, 'r') as fh:
        return fh.read().strip()


setup(name='itsy-init',
      version=get_version(),
      description='EC2 initialisation magic',
      author='Yahoo!',
      author_email='openstack-dev@yahoo-inc.com',
      packages=find_packages(),
      scripts=['itsy-init.py'],
      install_requires=parse_requires(),
      data_files=[('/etc/itsy', glob('config/*.cfg')),
                  ('/etc/itsy/itsy.cfg.d', glob('config/itsy.cfg.d/*')),
                  ('/etc/itsy/templates', glob('templates/*')),
                  ('/usr/share/itsy-init', []),
                  ('/usr/libexec/itsy-init', []),
                  ],
      )

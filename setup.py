#!/usr/bin/env python
# -*- coding: latin-1 -*-
#
# Copyright 2009-2012 Ghent University
# Copyright 2009-2012 Stijn De Weirdt
# Copyright 2012 Andy Georges
#
# This file is part of VSC-tools,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://vscentrum.be/nl/en),
# the Hercules foundation (http://www.herculesstichting.be/in_English)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# http://github.com/hpcugent/VSC-tools
#
# VSC-tools is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# VSC-tools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VSC-tools. If not, see <http://www.gnu.org/licenses/>.
#
"""
Setup for mympirun
"""
from shared_setup import action_target, sdw
from shared_setup_mympirun import mympirun_vsc_install_scripts

PACKAGE = {
    'name': 'vsc-mympirun',
    'install_requires': ['vsc-base >= 0.99'],
    'version': '3.1.0',
    'author': [sdw],
    'maintainer': [sdw],
    'packages': ['vsc.mympirun', 'vsc.mympirun.mpi', 'vsc.mympirun.rm', 'vsc.mympirun.external'],
    'py_modules': ['vsc.__init__'],
    'namespace_packages': ['vsc'],
    'scripts': ['bin/mympirun.py', 'bin/pbsssh.sh', 'bin/sshsleep.sh', 'bin/mympisanity.py'],
    'cmdclass': {
        "install_scripts": mympirun_vsc_install_scripts,
    },
}

if __name__ == '__main__':
    action_target(PACKAGE, extra_sdist=['shared_setup_mympirun.py'])

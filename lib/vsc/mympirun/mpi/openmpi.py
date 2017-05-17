#
# Copyright 2009-2017 Ghent University
#
# This file is part of vsc-mympirun,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# the Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# https://github.com/hpcugent/vsc-mympirun
#
# vsc-mympirun is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# vsc-mympirun is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with vsc-mympirun.  If not, see <http://www.gnu.org/licenses/>.
#
"""
OpenMPI specific classes

Documentation can be found at https://www.open-mpi.org/doc/
"""
import os
import subprocess

from vsc.mympirun.mpi.mpi import MPI


class OpenMPI(MPI):

    """An implementation of the MPI class for OpenMPI"""

    _mpiscriptname_for = ['ompirun']
    _mpirun_for = 'OpenMPI'

    DEVICE_MPIDEVICE_MAP = {'ib': 'sm,openib,self', 'det': 'sm,tcp,self', 'shm': 'sm,self', 'socket': 'sm,tcp,self'}

    MPIEXEC_TEMPLATE_GLOBAL_OPTION = "--mca %(name)s '%(value)s'"

    REMOTE_OPTION_TEMPLATE = "--mca pls_rsh_agent %(rsh)s"

    def set_mpiexec_global_options(self):
        """Set mpiexec global options"""
        self.mpiexec_global_options['btl'] = self.device

        super(OpenMPI, self).set_mpiexec_global_options()

    def _make_final_mpirun_cmd(self):
        """
        Create the acual mpirun command
        OpenMPI doesn't need mpdboot options
        """
        self.mpirun_cmd += self.mpiexec_options

    def pinning_override(self):
        """ pinning """

        override_type = self.pinning_override_type

        self.log.debug("pinning_override: type %s ", override_type)

        ranktxt = ""

        sockets_per_node = self.options.sockets
        if not sockets_per_node:
            try:
                proc_cpuinfo = open('/proc/cpuinfo').read()
            except IOError as err:
                self.log.debug("No info on sockets found; hardcoding to 2 (most likely)")
                sockets_per_node = 2

            if proc_cpuinfo:
                res = re.findall('^physical id.*', proc_cpuinfo, re.M)
                sockets_per_node = len(nub(res))
                self.log.debug("Sockets per node found in cpuinfo: set to %s" % sockets_per_node)

        universe = self.options.universe or len(self.nodes)

        try:
            rankfn = os.path.join(self.mympirundir, 'rankfile')

            if override_type in ('packed', 'compact', 'bunch'):
                # pack ranks, filling every consecutive slot on every consecutive node
                for rank in range(universe):
                    node = rank / self.ppn
                    socket = rank / (self.ppn / sockets_per_node)
                    slot = rank % (self.ppn / sockets_per_node)
                    ranktxt += "rank %i=+n%i slot=%i:%i\n" %(rank, node, socket, slot)

            elif override_type in ('spread', 'scatter'):
                #spread ranks evenly across nodes, but also spread them across sockets
                for rank in range(universe):
                    node = rank % len(self.nodes)
                    socket = (rank % self.ppn) % sockets_per_node
                    slot = (rank % self.ppn) / sockets_per_node
                    ranktxt += "rank %i=+n%i slot=%i:%i\n" %(rank, node, socket, slot)

            else:
                self.log.raiseException("pinning_override: unsupported pinning_override_type  %s" %
                                        self.pinning_override_type)

            open(rankfn, 'w').write(ranktxt)
            self.log.debug("pinning_override: wrote rankfile %s:\n%s", rankfn, ranktxt)
            cmd = "-rf %s" % rankfn

        except IOError:
            self.log.raiseException('pinning_override: failed to write rankfile %s' % rankfn)

        return cmd

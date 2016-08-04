#
# Copyright 2009-2016 Ghent University
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

from vsc.mympirun.mpi.mpi import MPI


class OpenMPI(MPI):

    """An implementation of the MPI class for OpenMPI"""

    _mpiscriptname_for = ['ompirun']
    _mpirun_for = ['OpenMPI']

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
          - add it to self.mpirun_cmd
          - No mpdboot for openmpi
        """
        self.mpirun_cmd += self.mpiexec_options

    def pinning_override(self):
        """ pinning """

        override_type = self.pinning_override_type

        self.log.debug("pinning_override: type %s ", override_type)

        ranktxt = ""

        sockets_per_node = 2

        try:
            rankfn = os.path.join(self.mympirundir, 'rankfile')

            if override_type in ('packed', 'compact', 'bunch'):


                ranktxt = "-rank-by core -bind-to core"
            elif override_type in ('spread', 'scatter'):
                if self.options.universe:
                    for rank in range(self.options.universe):
                        node = rank % self.nruniquenodes
                        socket = (rank % self.ppn) % sockets_per_node
                        slot = (rank % self.ppn) / sockets_per_node

                        ranktxt += "rank %i=+n%i slot=%i:%i\n" %(rank, node, socket, slot)
                        open(rankfn, 'w').write(ranktxt)
                        self.log.debug("pinning_override: wrote rankfile %s:\n%s", rankfn, ranktxt)
                        cmd = "-rf %s" % rankfn
                else:
                    cmd = "-bind-to core"

            else:
                self.log.raiseException("pinning_override: unsupported pinning_override_type  %s" %
                                        self.pinning_override_type)




        except IOError:
            self.log.raiseException('pinning_override: failed to write rankfile %s' % rankfn)

        return cmd

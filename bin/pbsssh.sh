#!/bin/bash
#
# Copyright 2009-2022 Ghent University
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

# - verified with Intel MPI mpdboot
# - also with Gaussian03 Linda (needs patch in linda_rsh)
# parse options

#
# parse extra VARS
#
extraenv=""
if [ ! -z "$PBSSSHENV" ]; then
    for v in $PBSSSHENV; do
        extraenv="$extraenv export $v=${!v} && "
    done
fi

while [ ! -z "$1" ] && [ "${1:0:1}" == "-" ]; do
    arg=$1
    shift
    case $arg in
        "-n")
        # -n: redirect stdin to /dev/null (used in mpdboot) -> ignore
        ;;
    esac
done

# cut nodenames
fullhost="$1"
shift 1

# is fullhost an ip address?

if tmphost=$(ipcalc -h "$fullhost" 2>&1); then
    # fullhost was an IP
    fullhost=${tmphost#*=}
fi

host=$fullhost

# postprocess options placed after the hostname?
#   cmd can't start with -X
while [ ! -z "$1" ] && [ "${1:0:1}" == "-" ]; do
    arg=$1
    shift
    case $arg in
        "-n")
        # -n: redirect stdin to /dev/null (used in mpdboot) -> ignore
	    ;;
    esac
done

## is needed to emulate the ssh nodeXXX which icc (w/o quotes)
cmd="$extraenv $@"

if [ "$PBSSSHMODE" == "ssh" ]; then
    ## plain old ssh mode
    ssh "$host" "$cmd"
elif command -v pbsdsh >&/dev/null; then
    # pbsdsh mode

    # uncomment for debugging
    #echo "ENTER PBSSSH"
    #echo pbsdsh -o -h "$host" bash -l -c "$cmd" >& /tmp/kk
    #echo pbsdsh -o -h "$host" bash -l -c "$cmd"
    #pbsdsh -o -h "$host" bash -l -c "$cmd" >> /tmp/kk 2>&1

    pbsdsh -o -h "$host" bash -l -c "$cmd"
    ec=$?
    if [ $ec -gt 0 ]; then
        # try again
        pbsdsh -o -h "$host" bash -l -c "$cmd"
        ec=$?
        if [ $ec -gt 0 ]; then
            echo "PBSSSH pbsdsh failed starting twice from host $(hostname) on host $host command \"$cmd\""
            exit $ec
        fi
    fi
elif command -v srun >& /dev/null; then
    srun -N 1 -n 1 --nodelist=$host --export=ALL /bin/bash -l -c "$cmd"
    ec=$?
    if [ $ec -gt 0 ]; then
        echo "PBSSSH srun failed starting from host $(hostname) on host $host command \"$cmd\""
        exit $ec
    fi
else
    echo "ERROR: pbsdsh not found."
    exit 10
fi

exit 0

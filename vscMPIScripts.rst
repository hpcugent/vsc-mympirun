======================
Writing MPI jobscripts
======================

Make sure you have read the User:VscScripts page. The general composition of MPI job scripts is identical to non-MPI versions. I.e. a similar job header must be written.


The mympirun wrapper
---------------------

Never call mpirun directly. We have written a wrapper, called mympirun, which is compatible with the Intel MPI, MVAPICH2 and OpenMPI implementations of MPI. mympirun automatically detects the required MPI implementation and translates this information in a correct mpirun call.

In your script, make sure the mympirun wrapper is loaded through `module load vsc-mympirun` after loading a compiler/MPI module (for example `intel` or `impi/5.0.3.048-GCC-4.9.3`).

Options
-------
General
'''''''
The options that can be passed to mympirun are:
::

    Usage: mympirun [options]


    Options:
      -u, --shorthelp       show short help message and exit
      -U OUTPUT_FORMAT, --help=OUTPUT_FORMAT
                            show full help message and exit
      --confighelp          show help as annotated configfile

      Debug and logging options (configfile section MAIN):
        -d, --debug         Enable debug log mode (def False)
        --info              Enable info log mode (def False)
        --quiet             Enable quiet/warning log mode (def False)

      Configfile options:
        --configfiles=CONFIGFILES
                            Parse (additional) configfiles (type comma-separated list)
        --ignoreconfigfiles=IGNORECONFIGFILES
                            Ignore configfiles (type comma-separated list)

      mympirun options:
        General advanced mympirun options (configfile section MAIN)

        --basepath=BASEPATH
                            Directory (preferably shared) to use for temporary mympirun files (default: HOME). (type str)
        --branchcount=BRANCHCOUNT
                            Set the hydra branchcount (type int)
        --debuglvl=DEBUGLVL
                            Specify debug level (type int; def 0)
        --debugmpi          Enable MPI level debugging (def False)
        --double            Run double the amount of processes (equivalent to --multi 2) (def False)
        -h HYBRID, --hybrid=HYBRID
                            Run in hybrid mode, specify number of processes per node. (type int)
        --launcher=LAUNCHER
                            The launcher to be used by Hydra (type str)
        --logtofile=LOGTOFILE
                            redirect the logging of mympirun to a file (instead of stdout/stderr) (type str)
        --mpdbootverbose    Run verbose mpdboot (def False)
        --mpirunoptions=MPIRUNOPTIONS
                            String with options to pass to mpirun (will be appended to generate command) (type str)
        --multi=MULTI       Run the amount of processes multiplied by the given integer (type int)
        --noenvmodules      Don't pass the environment modules variables (def False)
        --order=ORDER       Reorder the generated nodelist (default: normal. supports: sort, random[_<seed>]) (type str)
        --output=OUTPUT     redirect the output of mpirun to a file (instead of stdout/stderr) (type str)
        --output-check-fatal
                            Exit with code 124 instead of warn in case of output check timeout (def True)
        --output-check-timeout=OUTPUT-CHECK-TIMEOUT
                            Warn when no stdout/stderr was seen after start (in seconds; negative number disables this test (type int; def 3600)
        --overridepin=OVERRIDEPIN
                            Let mympriun set the affinity (default: disabled, left over to MPI implementation). Supported types: 'compact','spread','cycle' (add 'pin' postfix for single core pinning, e.g.
                            'cyclepin'). (type str)
        --pinmpi            Disable MPI pinning (def True)
        --rdma              Force rdma device
        -S SCHEDTYPE, --schedtype=SCHEDTYPE
                            Specify scheduler (eg local, pbs...; will try to guess by default). (type str)
        -M SETMPI, --setmpi=SETMPI
                            Specify MPI flavor (eg mpich2, openmpi...; will try to guess by default). (type str)
        -m, --showmpi       Print the known MPI classes and exit (def False)
        -s, --showsched     Print the known Sched classes and exit (def False)
        --socket            Force socket device
        --ssh               Force ssh for mpd startup (will try to use optimised method by default) (def True)
        --stats=STATS       Set MPI statistics level (type int; def 0)
        --universe=UNIVERSE
                            Start only this number of processes instead of all (e.g. for MPI_Spawn) Total size of the universe is all requested processes.) (type int)
        --use_psm           Use Performance Scaled Messaging
        --variablesprefix=VARIABLESPREFIX
                            Comma-separated list of exact names or prefixes to match environment variables (<prefix>_ should match) to pass through. (type string; def [])

      Intel MPI options:
        Advanced options specific for Intel MPI (configfile section impi)

        --impi-daplud       Enable DAPL UD connections (def False)
        --impi-fallback     Enable device fallback (def False)
        --impi-mpdbulletproof
                            Start MPD in bulletproof (def False)
        --impi-xrc          Enable Mellanox XRC (def False)

    Boolean options support disable prefix to do the inverse of the action, e.g. option --someopt also supports --disable-someopt.

    All long option names can be passed as environment variables. Variable name is MYMPIRUN_<LONGNAME> eg. --some-opt is same as setting MYMPIRUN_SOME_OPT in the environment.


Manipulating the number of processes
''''''''''''''''''''''''''''''''''''
With the options `double`, `multi`, `hybrid`, and `universe` you can manipulate the number of processes mympirun starts, different from the number of nodes.

* `double` starts twice the amount of processes.
* `multi n` starts `n` times the amount of processes. So `mympirun --multi 4` will start 4 times the amount of processes. `double` and `multi 2` are equivalent.
* `hybrid n` starts `n` processes on each physical node.
* `universe n` starts `n` processes in total.


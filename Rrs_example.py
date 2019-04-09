#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Example/Template for pytrios use

This is a partially tested configuration of the revamped library (Dec 2015)

Works for a set of SAM sensors connected through an IPS box.
Other uses may very well be buggy! Please file issues on github.

Call from command line with option -h for help

Example call:
python Rrs_example.py -COM 4 -vcom 1 -vchn 3 -samples 3 -rawout raw.txt -calpath calfiles -inttime 0 -plotting -calout cal.txt -plotting

Enjoy--
"""
from pytrios import PyTrios as ps
from pytrios import ramses_calibrate as rcal
#from pytrios import gpslib
import sys
import time
import datetime
import argparse
import serial
from numpy import arange, nan, isnan
import matplotlib.pyplot as plt
# force mathtext to use sans serif
plt.rcParams['mathtext.fontset'] = 'stixsans'
plt.rcParams['mathtext.default'] = 'regular'

prog = "pytrios v{0} by {1} ({2})".format(ps.__version__, ps.__author__,
                                          ps.__license__)


class TriosManager(object):
    """
    Trios manager class
    """

    def __init__(self, args):
        self.args = args

        # produce calibrated spectra?
        if self.args.calpath is not None:
            self.calibrate = True
            try:
                print("Looking for calibration files")
                self.caldict = rcal.importCalFiles(args.calpath)
            except Exception as m:
                print("Failed to import calibration files:\n{0}".format(m),
                    file=sys.stderr)
                sys.exit(1)
        else:
            self.calibrate = False

        # coms = []
        # # connect and start listening on specified COM port(s)
        # for arg in args.USB:
        #     coms.append(ps.TMonitor(arg, baudrate=9600))
        self.coms = ps.TMonitor(self.args.USB, baudrate=9600)
        #print(self.coms, file=sys.stdout)

        for com in self.coms:
            # set verbosity for com channel (com messages / errors)
            # 0/1/2 = none, errors, all
            com.verbosity = self.args.vcom

            # identify connected instruments
            ps.TCommandSend(com, commandset=None, command='query')
            time.sleep(1)  # wait for query results

        # identify SAM instruments from identified channels
        self.tk = list(ps.tchannels.keys())
        self.tc = ps.tchannels
        self.sams = [k for k in self.tk if ps.tchannels[k].TInfo.ModuleType in ['SAM', 'SAMIP']]  # keys
        self.chns = [self.tc[k].TInfo.TID for k in self.sams]  # channel addressing
        self.sns = [self.tc[k].TInfo.serialn for k in self.sams]  # sensor ids
        print("found SAM modules: {0}".format(list(zip(self.chns, self.sns))), file=sys.stdout)

        if len(self.sams) == 0:
            ps.TClose(self.coms)
            raise Exception("no SAM modules found")

        for s in self.sams:
            # 0/1/2/3/4 = none, errors, queries(default), measurements, all
            self.tc[s].verbosity = self.args.vchn  # set verbosity level for each sensor


    def run(self):

        counter = 0
        starttime = time.time()
        go = True

        while go:
        #while True:
            try:

                counter += 1
                for s in self.sams:
                    lasttrigger = datetime.datetime.now()
                    lasttrigstr = lasttrigger.isoformat()

                    if self.args.inttime > 0:
                        for com in self.coms:
                            # trigger single measurement at fixed integration time
                            self.tc[s].startIntSet(com, self.args.inttime, trigger=lasttrigger)
                    else:
                        for com in self.coms:
                            # trigger single measurement at auto integration time
                            self.tc[s].startIntAuto(com, trigger=lasttrigger)

                # follow progress
                npending = len(self.sams)
                while npending > 0:
                    nfinished = sum([1 for s in self.sams if self.tc[s].is_finished()])
                    npending = sum([1 for s in self.sams if self.tc[s].is_pending()])
                    # print(nfinished, npending)
                    time.sleep(0.05)

                # display some info:
                # how long did they take?
                delays = [self.tc[s].TSAM.lastRawSAMTime - lasttrigger for s in self.sams]
                delaysec = max([d.total_seconds() for d in delays])

                print("\t{0} spectra received, triggered at {1} ({2} s)"
                    .format(nfinished, lasttrigger, delaysec), file=sys.stdout)

                if nfinished == len(self.sams):
                    print("-{0}- All triggered measurements received"
                        .format(str(counter).zfill(4)),
                        file=sys.stdout)

                if nfinished == 0:
                    warningmsg = "No results received. Attempting to reconnect.. "
                    print(warningmsg, file=sys.stderr)
                    for com in self.coms:
                        # no response? re-send query to see who is still talking
                        ps.TCommandSend(com, commandset=None, command='query')
                        time.sleep(0.25)  # wait for query results
                    # identify SAM instruments from identified channels
                    self.tk = list(ps.tchannels.keys())
                    self.tc = ps.tchannels
                    self.sams = [k for k in self.tk if ps.tchannels[k].TInfo.ModuleType == 'SAM']
                    self.chns = [self.tc[k].TInfo.TID for k in self.sams]  # channel addressing
                    self.sns = [self.tc[k].TInfo.serialn for k in self.sams]  # sensor ids
                    print("found SAM modules: {0}".format(list(zip(self.chns, self.sns))),
                        file=sys.stdout)

                else:
                    # gather succesful results
                    specs = [self.tc[s].TSAM.lastRawSAM
                            for s in self.sams if self.tc[s].is_finished()]
                    sids = [self.tc[s].TInfo.serialn
                            for s in self.sams if self.tc[s].is_finished()]
                    itimes = [self.tc[s].TSAM.lastIntTime
                            for s in self.sams if self.tc[s].is_finished()]

                    if self.args.rawout is not None:
                        #  write raw data to specified file
                        for sp, si, it in zip(specs, sids, itimes):
                            outstr = ",".join([lasttrigstr,
                                            si, str(it),
                                            ",".join([str(s) for s in sp])])+'\n'
                            with open(self.args.rawout, 'a+') as f:
                                f.write(outstr)

                    if self.calibrate:  # get calibrated spectra
                        cspecs = []
                        wlOut = arange(320, 955, 3.3)
                        for spec, sid in zip(specs, sids):
                            try:
                                csp = rcal.raw2cal_Air(spec, lasttrigger,
                                                    sid, caldict,
                                                    wlOut=wlOut)
                                cspecs.append(csp)
                            except:
                                warnmsg = "Could not calibrate spectrum from {0}. Is calibration file present?".format(sid)
                                cspecs.append([nan]*len(wlOut))
                                print(warnmsg, file=sys.stderr)
                                pass

                    if self.calibrate and self.args.calout is not None:
                        #  write calibrated data to specified file
                        for sp, si, it in zip(cspecs, sids, itimes):
                            if sum([1 for s in sp if isnan(s)]) < len(sp):
                                outstr = ",".join([lasttrigstr,
                                                si, str(it),
                                                ",".join([str(s) for s in sp])])
                                outstr = outstr + '\n'
                                with open(self.args.calout, 'a+') as f:
                                    f.write(outstr)

                    if self.args.plotting:
                        # plot results
                        plt.ion()
                        fig = plt.figure(1)
                        fig.clf()
                        ax1 = fig.add_axes((0.1, 0.1, 0.8, 0.8))
                        if calibrate:  # get calibrated spectra
                            [ax1.plot(wlOut, cs, label=sid)
                            for cs, sid in zip(cspecs, sids)]
                        else:
                            [ax1.plot(sp, label=sid)
                            for sp, sid in zip(specs, sids)]
                        plt.title("spectrum {0} at {1}".format(counter, lasttrigger))
                        plt.legend()
                        plt.draw()
                        plt.pause(0.01)

                if (self.args.samples is not None and counter >= self.args.samples) or\
                        (self.args.period is not None and
                        ((time.time() - starttime)/60.0 >= self.args.period)):
                    go = False
            except:
                ps.TClose(self.coms)

                print("unexpected error!")
                raise
                sys.exit(1)
            # Cleanly close COM connections + listening threads

        # input('Press enter to close')
        # sys.exit(0)
        time.sleep(0.02)


    def __del__(self):
        ps.TClose(self.coms)



def parse_arguments():
    example = """Rrs_example 4 5 6 -vcom 1 -vchn 4 \
    -calpath calfiles -inttime 0 -period 10"""
    parser = argparse.ArgumentParser(description=None, epilog=example)
    parser.add_argument('USB', nargs='+', type=str,
                        help='Trios COM port(s)')
    parser.add_argument("-vcom", type=int, choices=[0, 1, 2, 3, 4],
                        help="set verbosity on COM objects", default=1)
    parser.add_argument("-vchn", type=int, choices=[0, 1, 2, 3, 4],
                        help="set verbosity on channel objects", default=3)
    parser.add_argument("-samples", type=int, default=None,
                        help="max number of repeat samples (default 10)")
    parser.add_argument("-period", type=int, default=None,
                        help="max period (minutes) to sample (default 1 min)")
    parser.add_argument("-rawout", type=str,
                        help="raw data output file")
    parser.add_argument("-calout", type=str,
                        help="calibrated data output file")
    parser.add_argument("-calpath", type=str,
                        help="path to search for calibration files")
    parser.add_argument("-inttime", type=int, default=0,
                        choices=[0, 4, 8, 16, 32, 64, 128, 256, 512, 1024,
                                2048, 4096, 8192],
                        help="Integration time in ms (0 = Auto)")
    parser.add_argument("-plotting", dest='plotting', action='store_true',
                        help="On-screen plotting (default off)")
    args = parser.parse_args()
    # set defaults for max sampling period and number if both are undefined
    if args.period is None and args.samples is None:
        args.samples = 20
        args.period = 1 * 60

    return args



if __name__ == '__main__':
    print(prog)
    args = parse_arguments()
    trios_manager = TriosManager(args)
    trios_manager.run()

#!/usr/bin/env python
# -*- coding: utf-8 -*-

# horepgd.py
#
# This script provides a daemon which runs daily

import argparse
import calendar
import datetime
try:
    import grp
except ModuleNotFoundError:
    print('ModuleNotFoundError: No module named \'grp\'. Daemonization not available on this OS.')
import logging
import logging.handlers
import os
try:
    import pwd
except ModuleNotFoundError:
    print('ModuleNotFoundError: No module named \'pwd\'. Daemonization not available on this OS.')
import sys
import time

from horepg.horizon import ChannelMap, Listings
from horepg.oorboekje import OorboekjeParser
from horepg.tvheadend import tvh_get_channels, TVHXMLTVSocket
from horepg.xmltvdoc import XMLTVDocument

def debug(msg):
    logging.debug(msg)

def info(msg):
    logging.info(msg)

def warning(msg):
    logging.warning(msg)

def switch_user(uid=None, gid=None):
    # set gid first
    if gid is not None:
        os.setgid(gid)
    if uid is not None:
        os.setuid(uid)

def daemonize():
    def fork_exit_parent():
        try:
            pid = os.fork()
            if pid > 0:
                # parent, so exit
                sys.exit(0)
        except OSError as exc:
            warning('Failed to fork parent process {:0}'.format(exc))
            sys.exit(1)
    def redirect_stream(source, target=None):
        if target is None:
            target_fd = os.open(os.devnull, os.O_RDWR)
        else:
            target_fd = target.fileno()
        os.dup2(target_fd, source.fileno())

    os.umask(0)
    os.chdir('/')

    fork_exit_parent()
    os.setsid()
    fork_exit_parent()

    # redirect streams
    sys.stdout.flush()
    sys.stderr.flush()
    redirect_stream(sys.stdin)
    redirect_stream(sys.stdout)
    redirect_stream(sys.stderr)

def run_import(wanted_channels, tvhsocket, fetch_radio=False, nr_days=5, output_folder=None):
    with TVHXMLTVSocket(tvhsocket) as tvh_client:
        # the Horizon API for TV channels
        chmap = ChannelMap()
        listings = Listings()
        # add listings for each of the channels
        for channel_id, channel in chmap.channels.items():
            if channel['title'].lower() in (wanted_channel.lower() for wanted_channel in wanted_channels):
                now = datetime.date.today().timetuple()
                number = 0
                xmltv = XMLTVDocument()
                xmltv.setDate(chmap.updated_time)

                # channel logo
                icon = None
                for asset in channel['images']:
                    if asset['assetType'] == 'focused':
                        icon = asset['url']
                        break

                suggested_channel_names = list()
                suggested_channel_names.append(channel['title'])
                if channel['channel_number']:
                    suggested_channel_names.append(str(channel['channel_number']))

                xmltv.addChannel(channel_id, suggested_channel_names, icon)

                # Fetch in blocks of 6 hours (8 hours is the maximum block size allowed)
                for i in range(0, nr_days*4):
                    start = int((calendar.timegm(now) + 21600 * i) * 1000) # milis
                    end = start + (21600 * 1000)
                    number = number + listings.obtain(xmltv, channel_id, start, end)

                debug('Adding {:d} programmes for channel {:s}'.format(number, channel['title']))

                if output_folder:
                    channel_name = channel['title'].lower().replace("/", "_")
                    try:
                        with open(os.path.join(output_folder, "{}.xml".format(channel_name)), 'wb', ) as fd:
                            fd.write(xmltv.document.toprettyxml(encoding='UTF-8'))
                    except OSError as exception:
                        # If we can't write output, warn the user and stop fetching/processing more channels.
                        warning(exception)
                        break
                else:
                    # send this channel to tvh for processing
                    tvh_client.send(xmltv.document.toprettyxml(encoding='UTF-8'))
        # Oorboekje for radio channels
        if fetch_radio:
            parser = OorboekjeParser()
            for i in range(0, nr_days):
                start = time.time() + i*86400 + 100
                tvh_client.send(parser.get_day(start))

def main():
    parser = argparse.ArgumentParser(description='Fetches EPG data from the Horizon service and passes it to TVHeadend.')
    parser.add_argument('-s', nargs='?', metavar='PATH', dest='tvhsocket', default='/home/hts/.hts/tvheadend/epggrab/xmltv.sock', type=str, help='path to TVHeadend XMLTV socket')
    parser.add_argument('-p', nargs='?', metavar='PATH', dest='pid_filename', default='/var/run/horepgd.pid', type=str, help='path to PID file')
    parser.add_argument('-u', nargs='?', metavar='USER', dest='as_user', default='hts', type=str, help='run as USER')
    parser.add_argument('-g', nargs='?', metavar='GROUP', dest='as_group', default='video', type=str, help='run as GROUP')
    parser.add_argument('-d', dest='daemonize', action='store_const', const=True, default=False, help='daemonize')
    parser.add_argument('-1', dest='single_shot', action='store_const', const=True, default=False, help='Run once, then exit')
    parser.add_argument('-nr', nargs='?', metavar='DAYS', dest='nr_days', default=5, type=int, help='Number of days to fetch')
    parser.add_argument('-tvh', dest='tvh_host', metavar='HOST', default='localhost', help='the hostname of TVHeadend to fetch channels from')
    parser.add_argument('-tvh_username', dest='tvh_username', metavar='USERNAME', type=str, default='', help='the username used to login into TVHeadend')
    parser.add_argument('-tvh_password', dest='tvh_password', metavar='PASSWORD', type=str, default='', help='the password used to login into TVHeadend')
    parser.add_argument('-R', dest='do_radio_epg', action='store_const', const=True, default=False, help='fetch EPG data for radio channels')
    parser.add_argument('-o', nargs='?', metavar='OUTPUTPATH', dest='output_path', default=None, type=str, help='so not send to TVHeadend but store to disk in OUTPUTPATH')
    args = parser.parse_args()

    if args.daemonize:
        if 'grp' in sys.modules and 'pwd' in sys.modules:
            # Detect Synology
            if os.path.isfile('/etc.defaults/synoinfo.conf'):
                # Use Synology Log Center syslog. For details: https://gist.github.com/thomazz-nl/093305c8d4b87fd00cd41036c333ab08
                syslog = logging.handlers.SysLogHandler(address='/var/run/syslog', facility=logging.handlers.SysLogHandler.LOG_USER)
                syslog.ident = 'System: '
                syslog.setFormatter(logging.Formatter('SYSTEM:	Package [HorEPG]: %(message)s'))

                root_logger = logging.getLogger()
                root_logger.addHandler(syslog)
                root_logger.setLevel(logging.INFO)
            else:
                # switch to syslog
                logging.basicConfig(stream=logging.handlers.SysLogHandler())

            # switch user and do daemonization
            try:
                uid = pwd.getpwnam(args.as_user).pw_uid
                gid = grp.getgrnam(args.as_group).gr_gid
            except (KeyError, AttributeError):
                warning('Unable to find the user {0} and/or group {1} for daemonization.'.format(args.as_user, args.as_group))
                sys.exit(1)

            pid_fd = open(args.pid_filename, 'w')

            switch_user(uid, gid)
            daemonize()
        else:
            warning('Daemonization failed. Try running without -d.')
            sys.exit(1)
    else:
        # Only call basicConfig once. Subsequent calls are ignored by default, unless forced by force=True.
        logging.basicConfig(level=logging.DEBUG)
        pid_fd = open(args.pid_filename, 'w')

    pid = str(os.getpid())
    pid_fd.write(pid + '\n')
    pid_fd.close()

    channels = tvh_get_channels(args.tvh_host, username=args.tvh_username, password=args.tvh_password)
    debug('Fetching listings for {:d} channels'.format(len(channels)))

    if args.single_shot:
        run_import(channels, args.tvhsocket, args.do_radio_epg, args.nr_days, args.output_path)
    else:
        while True:
            info('Fetching new EPG data.')
            run_import(channels, args.tvhsocket, args.do_radio_epg, args.nr_days)
            time.sleep(60*60*24)

if __name__ == '__main__':
    main()

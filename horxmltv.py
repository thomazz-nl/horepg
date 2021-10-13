#!/usr/bin/env python
# -*- coding: utf-8 -*-

from horepg.horizon import *
import logging

# the wanted channels
wanted_channels = ['TV Oost', 'ARD HD', '13TH Street HD', 'ZDF HD']

logging.basicConfig(level=logging.DEBUG)

if __name__ == '__main__':
  with open('tvguide.xml', 'w', encoding='UTF-8') as fd:
    print('Running horepg')
    chmap = ChannelMap()
    listings = Listings()
    xmltv = XMLTVDocument()
    xmltv.set_date(chmap.updated_time)

    # add listings for each of the channels
    for channel_id, channel in chmap.channels.items():
      if channel['title'] in wanted_channels:
        nr = 0
        now = datetime.date.today().timetuple()

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
        for i in range(0, 5*4):
          start = int((calendar.timegm(now) + 21600 * i) * 1000) # milis
          end = start + (21600 * 1000)
          nr = nr + listings.obtain(xmltv, channel_id, start, end)

        debug('Added {:d} programmes for channel {:s}'.format(nr, channel['title']))
    fd.write(xmltv.document.toprettyxml())

# -*- coding: utf-8 -*-

"""
Download EPG data from Horizon and output XMLTV stuff
"""

import logging
import time
import json
import http.client

def debug(msg):
    logging.debug(msg)

def debug_json(data):
    debug(json.dumps(data, sort_keys=True, indent=4))

class HorizonRequest(object):
    hosts = ['web-api-salt.horizon.tv', 'web-api-pepper.horizon.tv']

    def __init__(self):
        self.current = 0
        self.connection = http.client.HTTPSConnection(HorizonRequest.hosts[self.current])

    def request(self, method, path, retry=True):
        self.connection.request(method, path)
        response = self.connection.getresponse()
        if response.status == 500:
            debug('Failed to request data from Horizon API, HTTP status {:0}'.format(response.status))
            debug('Waiting for 5 seconds before trying again !')
            time.sleep(5)
            self.connection = http.client.HTTPSConnection(HorizonRequest.hosts[self.current])
            return self.request(method, path, retry=True)
        if response.status == 200:
            return response
        elif response.status == 403:
            # switch hosts
            debug('Switching hosts')
            if self.current == 0:
                self.current = 1
            else:
                self.current = 0
            self.connection = http.client.HTTPSConnection(HorizonRequest.hosts[self.current])
            if retry:
                return self.request(method, path, retry=False)
        else:
            debug('Failed to request data from Horizon API, HTTP status {:0}'.format(response.status))
        return response

class ChannelMap(object):
    path = '/oesp/api/NL/nld/web/channels/'

    def __init__(self):
        self.horizon_request = HorizonRequest()
        response = self.horizon_request.request('GET', ChannelMap.path)
        if response:
            raw = response.read()
        else:
            raise Exception('Failed to get data from Horizon API, HTTP status {:d}'.format(response.status))
        # load json
        data = json.loads(raw.decode('utf-8'))
        #setup channel map
        self.channels = {}
        self.updated_time = None
        if 'updated' in data:
            self.updated_time = data["updated"]
        for channel in data['channels']:
            for schedule in channel['stationSchedules']:
                station = schedule['station']
                if 'channelNumber' in channel:
                    station['channel_number'] = channel['channelNumber']
                self.channels[station['id']] = station           
    def dump(self, xmltv):
        for key, value in self.channels.items():
            xmltv.addChannel(value['id'], [value['title']])
    def lookup(self, channel_id):
        if channel_id in self.channels:
            return self.channels[channel_id]
        return False
    def lookup_by_title(self, title):
        for channel_id, channel in self.channels.items():
            if channel['title'] == title:
                return channel_id
        return False

class Listings(object):
    path = '/oesp/api/NL/nld/web/listings'

    """
    Defaults to only few days for given channel
    """
    def __init__(self):
        self.horizon_request = HorizonRequest()
    def obtain(self, xmltv, channel_id, start=False, end=False):
        if not start:
            start = int(time.time() * 1000)
        if not end:
            end = start + (86400 * 2 * 1000)
        path = Listings.path + '?byStationId=' + channel_id + '&byStartTime=' + str(start) + '~' + str(end) + '&sort=startTime'
        response = self.horizon_request.request('GET', path)
        if response:
            return parse(response.read(), xmltv)
        else:
            raise Exception('Failed to GET listings url:', response.status, response.reason)

def parse(raw, xmltv):
    # parse raw data
    data = json.loads(raw.decode('utf-8'))
    invalid = 0
    for listing in data['listings']:
        if not 'program' in listing:
            debug('Listing has no programme field')
            continue
        if not 'title' in listing['program']:
            debug('Listing has programme, but programme has no title')
            continue
        if 'geen info beschikbaar' == listing['program']['title'].lower():
            debug('Listing has programme, but programme has invalid title')
            invalid = invalid + 1
            continue

        start = int(listing['startTime']) / 1000
        end = int(listing['endTime']) / 1000
        channel_id = listing['stationId']
        title = listing['program']['title']

        if 'secondaryTitle' in listing['program']:
            secondary_title = listing['program']['secondaryTitle']
        else:
            secondary_title = None

        if 'longDescription' in listing['program']:
            description = listing['program']['longDescription']
        elif 'description' in listing['program']:
            description = listing['program']['description']
        elif 'shortDescription' in listing['program']:
            description = listing['program']['shortDescription']
        else:
            description = None

        if 'directors' in listing['program']:
            directors = listing['program']['directors']
        else:
            directors = list()

        if 'cast' in listing['program']:
            cast = listing['program']['cast']
        else:
            cast = list()

        if 'year' in listing['program']:
            copyright_year = listing['program']['year']
        else:
            copyright_year = None

        categories = list()
        if 'categories' in listing['program']:
            for cat in listing['program']['categories']:
                categories.append(cat['title'])

        language = None
        if 'audioTracks' in listing:
            for audio_track in listing['audioTracks']:
                if 'lang' in audio_track and 'audiopurpose' in audio_track and audio_track['audiopurpose'] == 'main':
                    language = audio_track['lang']
                    break

        images = list()
        if 'images' in listing['program']:
            image_priority_1 = None
            image_priority_2 = None
            image_priority_3 = None
            for image in listing['program']['images']:
                if 'assetType' in image and 'url' in image:
                    if image['assetType'] == 'HighResLandscape':
                        image_priority_2 = image['url']
                    #elif image['assetType'] == 'HighResLandscapeProductionStill':
                        # skip: stills of the videostream are not worth adding
                    elif image['assetType'] == 'HighResPortrait':
                        image_priority_1 = image['url']
                    elif image['assetType'] == 'TitleTreatment':
                        image_priority_3 = image['url']
            if image_priority_1:
                images.append(image_priority_1)
            if image_priority_2:
                images.append(image_priority_2)
            if image_priority_3:
                images.append(image_priority_3)

        if 'seriesEpisodeNumber' in listing['program']:
            try:
                tmp_episode_number = int(listing['program']['seriesEpisodeNumber'])
                # HorizonTV often has bad data as "seriesEpisodeNumber" (e.g. a date). Their website only handles programs as "_isEpisodeWithSeasons" when the episode number is lower than their "episodeNumberThreshold" (set at 99999).
                episode_number = str(tmp_episode_number-1) if tmp_episode_number > 0 and tmp_episode_number <= 99999 else ''
            except (ValueError, TypeError):
                episode_number = ''
        else:
            episode_number = ''

        if 'seriesNumber' in listing['program']:
            try:
                tmp_season_number = int(listing['program']['seriesNumber'])
                # Perform a sanity check for "seriesNumber" (season) in a similar fashion as we did for "seriesEpisodeNumber".
                season_number = str(tmp_season_number-1) if tmp_season_number > 0 and tmp_season_number <= 99999 else ''
            except (ValueError, TypeError):
                season_number = ''
        else:
            season_number = ''

        if season_number == '' and episode_number == '':
            episode = None
        else:
            # If we have any valid information, add it in the "xmltv_ns" format instead of the loose "onscreen" format. This format requires numbers to be zero-indexed (hence the -1 before).
            episode = season_number + ' . ' + episode_number + ' . '

        subtitles = list()
        if 'subtitleLanguages' in listing:
            for subtitle_language in listing['subtitleLanguages']:
                subtitles.append(subtitle_language)

        sign_languages = list()
        if 'signLanguages' in listing:
            for sign_language in listing['signLanguages']:
                sign_languages.append(sign_language)

        parental_rating = None
        if 'isAdult' in listing['program']:
            is_adult = listing['program']['isAdult']
        if 'parentalRating' in listing['program']:
            parental_rating = '18' if is_adult else listing['program']['parentalRating']

        xmltv.addProgramme(channel_id, title, start, end, cast, categories, copyright_year, description, directors, episode, images, language, secondary_title, subtitles, sign_languages, parental_rating)
    return len(data['listings']) - invalid

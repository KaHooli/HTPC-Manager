#!/usr/bin/env python
# -*- coding: utf-8 -*-

import cherrypy
import htpc
import re
import socket
import struct
from json import loads
from urllib2 import Request, urlopen, quote
from htpc.helpers import get_image, striphttp, joinArgs
import logging
import urllib
import base64
import platform
from cherrypy.lib.auth2 import require
import requests
import platform
from uuid import getnode
'''
Credits.

PlexGDM:
Based on PlexConect:
https://github.com/iBaa/PlexConnect/blob/master/PlexAPI.py
'''


class Plex(object):
    def __init__(self):
        self.logger = logging.getLogger('modules.plex')
        self.headers = None

        htpc.MODULES.append({
            'name': 'Plex',
            'id': 'plex',
            'test': htpc.WEBDIR + 'plex/ping',
            'fields': [
                {'type': 'bool', 'label': 'Enable', 'name': 'plex_enable'},

                {'type': 'select',
                 'label': 'Existing Servers',
                 'name': 'gdm_plex_servers',
                 'options': [
                        {'name': 'Select', 'value': 0}
                    ]
                },
                {'type': 'text', 'label': 'Menu name', 'name': 'plex_name'},
                {'type': 'text', 'label': 'IP / Host *', 'name': 'plex_host'},
                {'type': 'text', 'label': 'Port *', 'name': 'plex_port', 'placeholder': '32400'},
                {'type': 'text', 'label': 'Username (optional)', 'desc': 'Plex Home actived server req username', 'name': 'plex_username'},
                {'type': 'password', 'label': 'Password (optional)', 'desc': 'Plex Home actived server req password', 'name': 'plex_password'},
                {'type': 'text', 'label': 'Mac addr.', 'name': 'plex_mac'},
                {'type': 'bool', 'label': 'Hide watched', 'name': 'plex_hide_watched'},
                {'type': 'bool', 'label': 'Hide homemovies', 'name': 'plex_hide_homemovies'},
                {'type': 'bool', 'label': 'Disable image resize', 'name': 'plex_disable_img_resize'},
                {"type": "text", "label": "Reverse proxy link", "placeholder": "", "desc":"Reverse proxy link ex: https://plex.mydomain.com", "name": "plex_reverse_proxy_link"},

            ]
        })

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def ping(self, plex_host='', plex_port='', **kwargs):
        ''' Tests settings, returns server name on success and null on fail '''
        try:
            self.logger.debug('Testing Plex connectivity')
            url = 'http://%s:%s' % (plex_host, plex_port)
            self.logger.debug('Trying to contact Plex via %s' % url)
            request = loads(urlopen(Request(url, headers=self.getHeaders())).read())
            self.logger.info('Connected to the Plex Media Server %s at %s' % (request.get('friendlyName'), url))
            return True
        except:
            self.logger.error('Unable to contact Plex via %s' % url)
            return

    @cherrypy.expose()
    @require()
    def index(self):
        return htpc.LOOKUP.get_template('plex.html').render(scriptname='plex')

    @cherrypy.expose()
    @require()
    def webinterface(self):
        ''' Generate page from template '''
        plex_host = striphttp(htpc.settings.get('plex_host', 'localhost'))
        plex_port = htpc.settings.get('plex_port', '32400')

        url = 'http://%s:%s/web' % (plex_host, plex_port)

        if htpc.settins.get('plex_reverse_proxy_link'):
            url = htpc.settins.get('plex_reverse_proxy_link')
            return url

        raise cherrypy.HTTPRedirect(url)

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetRecentMovies(self, limit=5):
        ''' Get a list of recently added movies '''
        self.logger.debug('Fetching recent Movies')

        try:
            plex_host = striphttp(htpc.settings.get('plex_host', 'localhost'))
            plex_port = htpc.settings.get('plex_port', '32400')
            plex_hide_homemovies = htpc.settings.get('plex_hide_homemovies', False)
            movies = []
            checked_path = []

            for section in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                # Only check file paths once!
                if section['_children'][0]['path'] not in checked_path:
                    checked_path.append(section['_children'][0]['path'])

                    if section['type'] == 'movie':
                        if section['agent'] != 'com.plexapp.agents.none' or not plex_hide_homemovies:
                            for movie in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections/%s/all?type=1&sort=addedAt:desc&X-Plex-Container-Start=0&X-Plex-Container-Size=%s' % (plex_host, plex_port, section['key'], limit), headers=self.getHeaders())).read())['_children']:
                                jmovie = {}
                                genre = []

                                jmovie['title'] = movie['title']
                                jmovie['id'] = int(movie['ratingKey'])

                                if 'thumb'in movie:
                                    jmovie['thumbnail'] = movie['thumb']

                                if 'year'in movie:
                                    jmovie['year'] = movie['year']

                                if 'summary'in movie:
                                    jmovie['plot'] = movie['summary']

                                if 'duration'in movie:
                                    jmovie['runtime'] = int(movie['duration']) / 60000

                                if 'art'in movie:
                                    jmovie['fanart'] = movie['art']

                                if 'addedAt'in movie:
                                    jmovie['addedAt'] = movie['addedAt']

                                for attrib in movie['_children']:
                                    if attrib['_elementType'] == 'Genre':
                                        genre.append(attrib['tag'])

                                jmovie['genre'] = [genre]

                                movies.append(jmovie)

            return {'movies': sorted(movies, key=lambda k: k['addedAt'], reverse=True)[:int(limit)]}
        except Exception as e:
            self.logger.error('Unable to fetch recent movies! Exception: %s' % e)
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetRecentShows(self, limit=5):
        ''' Get a list of recently added shows '''
        try:
            plex_host = htpc.settings.get('plex_host', 'localhost')
            plex_port = htpc.settings.get('plex_port', '32400')
            episodes = []
            checked_path = []
            sec = []

            for section in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                # Only check file paths once!
                sec.append(section)
                if section['_children'][0]['path'] not in checked_path:
                    checked_path.append(section['_children'][0]['path'])

                    if section['type'] == 'show':
                        for episode in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections/%s/all?type=4&sort=addedAt:desc&X-Plex-Container-Start=0&X-Plex-Container-Size=%s' % (plex_host, plex_port, section['key'], limit), headers=self.getHeaders())).read())['_children']:
                            try:
                                jepisode = {}

                                jepisode['label'] = '%sx%s. %s' % (episode['parentIndex'], episode['index'], episode['title'])
                                jepisode['id'] = int(episode['ratingKey'])

                                if 'summary'in episode:
                                    jepisode['plot'] = episode['summary']

                                if 'index'in episode:
                                    jepisode['episode'] = episode['index']

                                if 'parentIndex'in episode:
                                    jepisode['season'] = episode['parentIndex']

                                if 'grandparentTitle'in episode:
                                    jepisode['showtitle'] = episode['grandparentTitle']

                                if 'duration'in episode:
                                    jepisode['runtime'] = int(episode['duration']) / 60000

                                if 'thumb'in episode:
                                    jepisode['fanart'] = episode['thumb']

                                if 'addedAt'in episode:
                                    jepisode['addedAt'] = episode['addedAt']

                                episodes.append(jepisode)
                            except Exception as e:
                                self.logger.debug("Failed looping ep %s %s" % (episode, e))
                                continue

            return {'episodes': sorted(episodes, key=lambda k: k['addedAt'], reverse=True)[:int(limit)]}
        except Exception as e:
            self.logger.error('Unable to fetch episodes! Exception: %s' % s)
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetRecentAlbums(self, limit=5):
        ''' Get a list of recently added albums '''
        try:
            plex_host = htpc.settings.get('plex_host', 'localhost')
            plex_port = htpc.settings.get('plex_port', '32400')
            albums = []
            checked_path = []

            for section in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                # Only check file paths once!
                if section['_children'][0]['path'] not in checked_path:
                    checked_path.append(section['_children'][0]['path'])

                    if section['type'] == 'artist':
                        for album in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections/%s/recentlyAdded?X-Plex-Container-Start=0&X-Plex-Container-Size=%s' % (plex_host, plex_port, section['key'], limit), headers=self.getHeaders())).read())['_children']:
                            jalbum = {}

                            jalbum['title'] = album['title']
                            jalbum['id'] = album['ratingKey']

                            if 'thumb'in album:
                                jalbum['thumbnail'] = album['thumb']

                            if 'parentTitle'in album:
                                jalbum['artist'] = album['parentTitle']

                            if 'year'in album:
                                jalbum['year'] = album['year']

                            if 'addedAt'in album:
                                jalbum['addedAt'] = album['addedAt']

                            albums.append(jalbum)

            return {'albums': sorted(albums, key=lambda k: k['addedAt'], reverse=True)[:int(limit)]}
        except Exception as e:
            self.logger.error('Unable to fetch albums! Exception: %s' % e)
            return

    @cherrypy.expose()
    @require()
    def GetThumb(self, thumb=None, h=None, w=None, o=100):
        ''' Parse thumb to get the url and send to htpc.proxy.get_image '''
        if htpc.settings.get('plex_disable_img_resize', False):
            self.logger.debug("Image resize is disabled")
            h = None
            w = None

        if thumb:
            if o >= 100:
                url = 'http://%s:%s%s' % (htpc.settings.get('plex_host', 'localhost'), htpc.settings.get('plex_port', '32400'), thumb)
                self.logger.debug('pil')
            else:
                # If o < 100 transcode on Plex server to widen format support
                url = 'http://%s:%s/photo/:/transcode?height=%s&width=%s&url=%s' % (htpc.settings.get('plex_host', 'localhost'), htpc.settings.get('plex_port', '32400'), h, w, urllib.quote_plus('http://%s:%s%s' % (htpc.settings.get('plex_host', 'localhost'), htpc.settings.get('plex_port', '32400'), thumb)))
                h = None
                w = None
                self.logger.debug("transcode")
        else:
            url = '/images/DefaultVideo.png'

        self.logger.debug('Trying to fetch image via %s' % url)
        return get_image(url, h, w, o, headers=self.getHeaders())

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetMovies(self, start=0, end=0, hidewatched=0):
        ''' Get a list movies '''
        self.logger.debug('Fetching Movies')

        try:
            plex_host = htpc.settings.get('plex_host', 'localhost')
            plex_port = htpc.settings.get('plex_port', '32400')
            plex_hide_homemovies = htpc.settings.get('plex_hide_homemovies', False)
            movies = []
            limits = {}
            checked_path = []
            dupe_check = []
            sortedmovies = []

            if hidewatched == '1':
                hidewatched = 'unwatched'
            else:
                hidewatched = 'all'

            for section in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                # Only check file paths once!
                if section['_children'][0]['path'] not in checked_path:
                    checked_path.append(section['_children'][0]['path'])

                    if section['type'] == 'movie':
                        if section['agent'] != 'com.plexapp.agents.none' or not plex_hide_homemovies:
                            for movie in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections/%s/%s' % (plex_host, plex_port, section['key'], hidewatched), headers=self.getHeaders())).read())['_children']:
                                if movie['title'] not in dupe_check:
                                    dupe_check.append(movie['title'])

                                    jmovie = {}
                                    genre = []
                                    jmovie['playcount'] = 0
                                    jmovie['id'] = int(movie['ratingKey'])

                                    if 'titleSort' not in movie:
                                        jmovie['titlesort'] = movie['title']

                                    if 'titleSort' in movie:
                                        jmovie['titlesort'] = movie['titleSort']

                                    jmovie['title'] = movie['title']
                                    if 'thumb'in movie:
                                        jmovie['thumbnail'] = movie['thumb']

                                    if 'year'in movie:
                                        jmovie['year'] = int(movie['year'])

                                    if 'summary'in movie:
                                        jmovie['plot'] = movie['summary']

                                    if 'studio'in movie:
                                        jmovie['studio'] = movie['studio']

                                    if 'duration'in movie:
                                        jmovie['runtime'] = int(movie['duration']) / 60000

                                    if 'art'in movie:
                                        jmovie['fanart'] = movie['art']

                                    if 'rating'in movie:
                                        jmovie['rating'] = movie['rating']

                                    if 'viewCount' in movie:
                                        jmovie['playcount'] = int(movie['viewCount'])

                                    for attrib in movie['_children']:
                                        if attrib['_elementType'] == 'Genre':
                                            genre.append(attrib['tag'])

                                    if len(genre) != 0:
                                        jmovie['genre'] = genre

                                    movies.append(jmovie)

                                else:
                                    continue

            limits['start'] = int(start)
            limits['total'] = len(movies)
            limits['end'] = int(end)
            if int(end) >= len(movies):
                limits['end'] = len(movies)

            sortedmovies = sorted(movies, key=lambda k: k['titlesort'])

            return {'limits': limits, 'movies': sortedmovies[int(start):int(end)]}
        except Exception as e:
            self.logger.error('Unable to fetch all movies! Exception: %s' % e)
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetShows(self, start=0, end=0, hidewatched=0):
        ''' Get a list of shows '''
        try:
            plex_host = htpc.settings.get('plex_host', '')
            plex_port = htpc.settings.get('plex_port', '32400')
            tvShows = []
            limits = {}
            checked_path = []
            dupe_check = []
            sortedshows = []

            if hidewatched == '1':
                hidewatched = 'unwatched'
            else:
                hidewatched = 'all'

            for section in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                # Only check file paths once!
                if section['_children'][0]['path'] not in checked_path:
                    checked_path.append(section['_children'][0]['path'])

                    if section['type'] == 'show':
                        for tvShow in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections/%s/%s' % (plex_host, plex_port, section['key'], hidewatched), headers=self.getHeaders())).read())['_children']:
                            # Only allow unique showname in dupecheck
                            if tvShow['title'] not in dupe_check:
                                dupe_check.append(tvShow['title'])
                                jshow = {}
                                jshow['itemcount'] = 0
                                jshow['playcount'] = 0

                                # Since titleSort only exist in titles like the showname etc
                                # Set title as titlesort
                                if 'titleSort' not in tvShow:
                                    jshow['titlesort'] = tvShow['title']

                                if 'titleSort' in tvShow:
                                    jshow['titlesort'] = tvShow['titleSort']

                                jshow['title'] = tvShow['title']

                                jshow['id'] = tvShow['ratingKey']

                                if 'thumb'in tvShow:
                                    jshow['thumbnail'] = tvShow['thumb']

                                if 'year'in tvShow:
                                    jshow['year'] = int(tvShow['year'])

                                if 'summary'in tvShow:
                                    jshow['plot'] = tvShow['summary']

                                if 'viewedLeafCount'in tvShow:
                                    jshow['playcount'] = int(tvShow['viewedLeafCount'])

                                if 'leafCount'in tvShow:
                                    jshow['itemcount'] = int(tvShow['leafCount'])

                                tvShows.append(jshow)
                            else:
                                continue

            limits['start'] = int(start)
            limits['total'] = len(tvShows)
            limits['end'] = int(end)
            if int(end) >= len(tvShows):
                limits['end'] = len(tvShows)

            # sort the shows before return
            sortedshows = sorted(tvShows, key=lambda k: k['titlesort'])

            return {'limits': limits, 'tvShows': sortedshows[int(start):int(end)]}

        except Exception as e:
            self.logger.error('Unable to fetch all shows! Exception: %s' % e)
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetArtists(self, start=0, end=0):
        ''' Get a list of recently added artists '''
        try:
            plex_host = htpc.settings.get('plex_host', '')
            plex_port = htpc.settings.get('plex_port', '32400')
            artists = []
            limits = {}
            checked_path = []
            dupe_check = []
            sortedartist = []

            for section in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                # Only check file paths once!
                if section['_children'][0]['path'] not in checked_path:
                    checked_path.append(section['_children'][0]['path'])
                    if section['type'] == 'artist':
                        for artist in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections/%s/all' % (plex_host, plex_port, section['key']), headers=self.getHeaders())).read())['_children']:
                            if artist['title'] not in dupe_check:
                                dupe_check.append(artist['title'])
                                # Since titleSort only exist in titles like the xx etc
                                # Set title as titlesort
                                if 'titleSort' not in artist:
                                    jartist['titlesort'] = artist['title']

                                if 'titleSort' in artist:
                                    jartist['titlesort'] = artist['titleSort']
                                genre = []
                                jartist = {}
                                jartist['title'] = artist['title']
                                jartist['id'] = artist['ratingKey']

                                artists.append(jartist)
                            else:
                                continue

            limits['start'] = int(start)
            limits['total'] = len(artists)
            limits['end'] = int(end)
            if int(end) >= len(artists):
                limits['end'] = len(artists)

            sortedartist = sorted(artists, key=lambda k: k['titlesort'])

            return {'limits': limits, 'artists': sortedartist[int(start):int(end)]}
        except Exception as e:
            self.logger.error('Unable to fetch all artists! Exception: %s' % s)
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetAlbums(self, start=0, end=0, artistid=''):
        ''' Get a list of Albums '''
        try:
            plex_host = htpc.settings.get('plex_host', '')
            plex_port = htpc.settings.get('plex_port', '32400')
            albums = []
            limits = {}
            checked_path = []

            for section in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                # Only check file paths once!
                if section['_children'][0]['path'] not in checked_path:
                    checked_path.append(section['_children'][0]['path'])

                    if section['type'] == 'artist':
                        for album in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections/%s/albums' % (plex_host, plex_port, section['key']), headers=self.getHeaders())).read())['_children']:
                            if (str(album['parentRatingKey']) == artistid) or (artistid == ''):
                                jalbum = {}

                                jalbum['title'] = album['title']

                                jalbum['id'] = album['ratingKey']

                                if 'thumb'in album:
                                    jalbum['thumbnail'] = album['thumb']

                                albums.append(jalbum)

            limits['start'] = int(start)
            limits['total'] = len(albums)
            limits['end'] = int(end)
            if int(end) >= len(albums):
                limits['end'] = len(albums)

            return {'limits': limits, 'albums': sorted(albums, key=lambda k: k['title'])[int(start):int(end)]}
        except Exception as e:
            self.logger.error('Unable to fetch all Albums! Exception: %s' % e)
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetSongs(self, start=0, end=0, albumid=''):
        ''' Get a list of songs '''
        try:
            plex_host = htpc.settings.get('plex_host', '')
            plex_port = htpc.settings.get('plex_port', '32400')
            songs = []
            limits = {}
            checked_path = []

            if albumid != '':
                request = self.JsonLoader(urlopen(Request('http://%s:%s/library/metadata/%s/children' % (plex_host, plex_port, albumid), headers=self.getHeaders())).read())
                for song in request['_children']:
                    jsong = {}

                    try:
                        jsong['artist'] = song['originalTitle']
                    except:
                        jsong['artist'] = request['title1']

                    jsong['label'] = song['title']

                    jsong['album'] = request['parentTitle']

                    jsong['id'] = song['ratingKey']
                    try:
                        jsong['duration'] = song['duration'] / 1000
                    except:
                        pass

                    songs.append(jsong)
            else:

                for section in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                    # Only check file paths once!
                    if section['_children'][0]['path'] not in checked_path:
                        checked_path.append(section['_children'][0]['path'])

                        if section['type'] == 'artist':

                            for song in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections/%s/search?type=10' % (plex_host, plex_port, section['key']), headers=self.getHeaders())).read())['_children']:
                                jsong = {}

                                jsong['artist'] = song['grandparentTitle']
                                jsong['label'] = song['title']

                                jsong['album'] = song['parentTitle']

                                jsong['id'] = song['ratingKey']
                                try:
                                    jsong['duration'] = song['duration'] / 1000
                                except:
                                    pass

                                songs.append(jsong)

            limits['start'] = int(start)
            limits['total'] = len(songs)
            limits['end'] = int(end)
            if int(end) >= len(songs):
                limits['end'] = len(songs)

            return {'limits': limits, 'songs': songs[int(start):int(end)]}
        except Exception as e:
            self.logger.error('Unable to fetch all songs! Exception: %s' % e)
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetEpisodes(self, start=0, end=0, tvshowid=None, hidewatched=0):
        ''' Get information about a single TV Show '''
        self.logger.debug('Loading information for TVID %s' % tvshowid)
        try:
            plex_host = htpc.settings.get('plex_host', '')
            plex_port = htpc.settings.get('plex_port', '32400')
            episodes = []
            limits = {}

            for episode in self.JsonLoader(urlopen(Request('http://%s:%s/library/metadata/%s/allLeaves' % (plex_host, plex_port, tvshowid), headers=self.getHeaders())).read())['_children']:
                jepisode = {}
                jepisode['playcount'] = 0

                jepisode['label'] = '%sx%s. %s' % (episode['parentIndex'], episode['index'], episode['title'])
                jepisode['id'] = episode['ratingKey']

                if 'summary'in episode:
                    jepisode['plot'] = episode['summary']

                if 'grandparentTitle'in episode:
                    jepisode['showtitle'] = episode['grandparentTitle']

                if 'index'in episode:
                    jepisode['episode'] = episode['index']

                if 'parentIndex'in episode:
                    jepisode['season'] = episode['parentIndex']

                if 'viewCount'in episode:
                    jepisode['playcount'] = int(episode['viewCount'])

                if 'thumb'in episode:
                    jepisode['thumbnail'] = episode['thumb']

                if 'rating'in episode:
                    jepisode['rating'] = episode['rating']

                if hidewatched == '1':
                    if jepisode['playcount'] <= 0:
                        episodes.append(jepisode)
                else:
                    episodes.append(jepisode)

            limits['start'] = int(start)
            limits['total'] = len(episodes)
            limits['end'] = int(end)
            # TODO plocka total from headern.
            if int(end) >= len(episodes):
                limits['end'] = len(episodes)

            return {'limits': limits, 'episodes': episodes[int(start):int(end)]}
        except Exception as e:
            self.logger.error('Unable to fetch all episodes! Exception: %s' % e)
            return

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def Wake(self):
        ''' Send WakeOnLan package '''
        self.logger.info('Waking up Plex Media Server')
        try:
            addr_byte = htpc.settings.get('plex_mac', '').split(':')
            hw_addr = struct.pack('BBBBBB',
            int(addr_byte[0], 16),
            int(addr_byte[1], 16),
            int(addr_byte[2], 16),
            int(addr_byte[3], 16),
            int(addr_byte[4], 16),
            int(addr_byte[5], 16))
            msg = '\xff' * 6 + hw_addr * 16
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(msg, ('255.255.255.255', 9))
            self.logger.info('WOL package sent to %s' % htpc.settings.get('plex_mac', ''))
            return 'WOL package sent'
        except Exception as e:
            self.logger.debug('Exception: %s' % e)
            self.logger.error('Unable to send WOL packet')
            return 'Unable to send WOL packet'

    def JsonLoader(self, s):
        """ Try to repair the Json returned from Plex """
        while True:
            try:
                result = loads(s)   # try to parse...
                break                    # parsing worked -> exit loop
            except Exception as e:
                unexp = int(re.findall(r'\(char (\d+)\)', str(e))[0])
                # position of unescaped '"' before that
                unesc = s.rfind(r'"', 0, unexp)
                s = s[:unesc] + r'\"' + s[unesc + 1:]
                # position of correspondig closing '"' (+2 for inserted '\')
                closg = s.find(r'"', unesc + 2)
                s = s[:closg] + r'\"' + s[closg + 1:]
        return result

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def myPlexSignin(self, username='', password=''):
        try:

            username = htpc.settings.get('plex_username', '')
            password = htpc.settings.get('plex_password', '')

            if username and password:
                self.logger.debug('Fetching auth token')
                headers = {}
                headers['Authorization'] = 'Basic %s' % base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
                headers['X-Plex-Client-Identifier'] = str(hex(getnode()))
                headers['X-Plex-Product'] = 'HTPC-Manager'
                headers['X-Plex-Device'] = 'HTPC-Manager'
                headers['X-Plex-Version'] = '1.0'
                headers['X-Plex-Device-Name'] = socket.gethostname()
                headers['X-Plex-Platform'] = platform.system()
                headers['X-Plex-Client-Platform'] = platform.system()
                headers['X-Plex-Platform-Version'] = platform.version()
                headers['X-Plex-Provides'] = 'controller'
                r = Request('https://plex.tv/users/sign_in.xml', data='', headers=headers)
                r = urlopen(r)

                compiled = re.compile('<authentication-token>(.*)<\/authentication-token>', re.DOTALL)
                authtoken = compiled.search(r.read()).group(1).strip()

                if authtoken is not None:
                    htpc.settings.set('plex_authtoken', authtoken)
                    return 'Logged in to myPlex'
                else:
                    return 'Failed to loggin to myPlex'
            else:
                if not htpc.settings.get('plex_authtoken', ''):
                    htpc.settings.set('plex_authtoken', '')
                    self.logger.debug('Removed myPlex Token')
                return
        except Exception as e:
            self.logger.error('Exception: ' + str(e))
            return 'Failed to logg in to myPlex: %s' % str(e)

    def getHeaders(self):
        if self.headers is None:
            # Make headers if they dont exist
            authtoken = htpc.settings.get('plex_authtoken', '')
            username = htpc.settings.get('plex_username', '')
            password = htpc.settings.get('plex_password', '')

            # Dont try fetch token untelss you have u/p
            if not authtoken and username and password:
                self.myPlexSignin()
                authtoken = htpc.settings.get('plex_authtoken', '')

            headers = {'Accept': 'application/json'}

            headers["X-Plex-Provides"] = 'controller'
            headers["X-Plex-Platform"] = platform.uname()[0]
            headers["X-Plex-Platform-Version"] = platform.uname()[2]
            headers['X-Plex-Product'] = 'HTPC-Manager'
            headers['X-Plex-Version'] = '0.9.5'
            headers['X-Plex-Device'] = platform.platform()
            headers['X-Plex-Client-Identifier'] = str(hex(getnode()))

            if authtoken:
                headers['X-Plex-Token'] = authtoken
            if username:
                headers['X-Plex-Username'] = username
            self.headers = headers
            return headers
        else:
            return self.headers

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def NowPlaying(self):
        ''' Get information about current playing item '''
        #self.logger.debug('Fetching currently playing information')
        playing_items = []

        try:
            plex_host = htpc.settings.get('plex_host', '')
            plex_port = htpc.settings.get('plex_port', '32400')

            for video in self.JsonLoader(urlopen(Request('http://%s:%s/status/sessions' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                jplaying_item = {}
                jplaying_item['protocolCapabilities'] = []

                if 'index' in video:
                    jplaying_item['episode'] = int(video['index'])
                if 'parentThumb' in video:
                    jplaying_item['fanart'] = video['parentThumb']
                jplaying_item['thumbnail'] = video['thumb']
                if 'parentIndex' in video:
                    jplaying_item['season'] = int(video['parentIndex'])
                jplaying_item['title'] = video['title']
                if 'year' in video:
                    jplaying_item['year'] = int(video['year'])
                jplaying_item['id'] = int(video['ratingKey'])
                jplaying_item['type'] = video['type']
                if 'grandparentTitle' in video:
                    jplaying_item['show'] = video['grandparentTitle']
                jplaying_item['duration'] = int(video['duration'])
                try:
                    jplaying_item['viewOffset'] = int(video['viewOffset'])
                except:
                    jplaying_item['viewOffset'] = 0

                for children in video['_children']:
                    if children['_elementType'] == 'Player':
                        jplaying_item['state'] = children['state']
                        jplaying_item['player'] = children['title']
                        # We need some more info to see what the client supports
                        for client in self.JsonLoader(urlopen(Request('http://%s:%s/clients' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                            if client['machineIdentifier'] == children['machineIdentifier']:
                                jplaying_item['protocolCapabilities'] = client['protocolCapabilities'].split(',')
                                jplaying_item['address'] = client['address']

                    if children['_elementType'] == 'User':
                        if 'title' in children:
                            jplaying_item['user'] = children['title']
                        if 'thumb' in children:
                            jplaying_item['avatar'] = children['thumb']

                # Sometimes the client doesn't send the last timeline event. Ignore all client that almost have played the entire lenght.
                if jplaying_item['viewOffset'] < (int(jplaying_item['duration']) - 10000):
                    playing_items.append(jplaying_item)

        except Exception as e:
            self.logger.error('Unable to fetch currently playing information! Exception: %s' % e)
            pass
        return {'playing_items': playing_items}

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def UpdateLibrary(self, section_type=None):
        ''' Get information about current playing item '''
        self.logger.debug('Updating Plex library')
        try:
            plex_host = htpc.settings.get('plex_host', '')
            plex_port = htpc.settings.get('plex_port', '32400')

            for section in self.JsonLoader(urlopen(Request('http://%s:%s/library/sections' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                if section_type is None or section_type == section['type']:
                    self.logger.debug('Updating section %s' % section['key'])
                    try:
                        urllib.urlopen('http://%s:%s/library/sections/%s/refresh' % (plex_host, plex_port, section['key']))
                    except Exception as e:
                        self.logger.error('Failed to update section %s on Plex: %s' % (section['key'], e))
            return 'Update command sent to Plex'
        except Exception as e:
            self.logger.error('Failed to update library! Exception: %s' % e)
            return 'Failed to update library!'

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def ControlPlayer(self, player, action, value=''):
        ''' Various commands to control Plex Player '''
        self.logger.debug('Sending %s to %s value %s: ' % (action, player, value))
        try:

            self.navigationCommands = ['moveUp', 'moveDown', 'moveLeft', 'moveRight', 'pageUp', 'pageDown', 'nextLetter', 'previousLetter', 'select', 'back', 'contextMenu', 'toggleOSD']
            self.playbackCommands = ['play', 'pause', 'stop', 'rewind', 'fastForward', 'stepForward', 'bigStepForward', 'stepBack', 'bigStepBack', 'skipNext', 'skipPrevious']
            self.applicationCommands = ['playFile', 'playMedia', 'screenshot', 'sendString', 'sendKey', 'sendVirtualKey', 'setVolume']

            plex_host = htpc.settings.get('plex_host', '')
            plex_port = htpc.settings.get('plex_port', '32400')
            if action in self.navigationCommands:
                urllib.urlopen('http://%s:%s/system/players/%s/naviation/%s' % (plex_host, plex_port, player, action))
            elif action in self.playbackCommands:
                urllib.urlopen('http://%s:%s/system/players/%s/playback/%s' % (plex_host, plex_port, player, action))
            elif action.split('?')[0] in self.applicationCommands:
                urllib.urlopen('http://%s:%s/system/players/%s/application/%s' % (plex_host, plex_port, player, action))
            else:
                raise ValueError('Unable to control Plex with action: %s' % action)

        except Exception as e:
            self.logger.debug('Exception: %s' % e)
            #self.logger.error('Unable to control Plex with action: ' + action)
            self.logger.debug('Unable to control %s to %s value %s' % (action, player, value))
            return 'error'

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetPlayers(self, filter=None):
        ''' Get list of active Players '''
        self.logger.debug('Getting players from Plex')
        try:

            plex_host = htpc.settings.get('plex_host', '')
            plex_port = htpc.settings.get('plex_port', '32400')
            players = []
            players2 = []
            for player in self.JsonLoader(urlopen(Request('http://%s:%s/clients' % (plex_host, plex_port), headers=self.getHeaders())).read())['_children']:
                players2.append(player)

                try:
                    del player['_elementType']
                except:
                    pass

                if 'protocolCapabilities' in player:
                    player['protocolCapabilities'] = player['protocolCapabilities'].split(',')
                if filter == None or filter in player['protocolCapabilities']:
                    players.append(player)
            self.logger.debug(players2)
            return {'players': players}

        except Exception as e:
            self.logger.debug('Exception: %s' % e)
            self.logger.error('Unable to get players')
            return 'error'

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def GetServers(self, id=None):
        ''' Get list of servers '''
        self.logger.debug('Getting servers from Plex')
        try:

            IP_PlexGDM = '<broadcast>'
            Port_PlexGDM = 32414
            Msg_PlexGDM = 'M-SEARCH * HTTP/1.0'

            # setup socket for discovery -> multicast message
            GDM = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            GDM.settimeout(1.0)

            # Set the time-to-live for messages to 1 for local network
            GDM.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            returnData = []
            try:
                # Send data to the multicast group
                self.logger.info('Sending discovery message: %s' % Msg_PlexGDM)
                GDM.sendto(Msg_PlexGDM, (IP_PlexGDM, Port_PlexGDM))

                # Look for responses from all recipients
                while True:
                    try:
                        data, server = GDM.recvfrom(1024)
                        self.logger.debug('Received data from %s' % str(server))
                        self.logger.debug('Data received: %s' % str(data))
                        returnData.append( { 'from' : server,
                                             'data' : data } )
                    except socket.timeout:
                        break
            finally:
                GDM.close()

            discovery_complete = True

            PMS_list = []
            if returnData:
                for response in returnData:
                    update = {'ip': response.get('from')[0]}

                    # Check if we had a positive HTTP response
                    if '200 OK' in response.get('data'):
                        for each in response.get('data').split('\n'):
                            # decode response data

                            if 'Content-Type:' in each:
                                update['content-type'] = each.split(':')[1].strip()
                            elif 'Resource-Identifier:' in each:
                                update['uuid'] = each.split(':')[1].strip()
                            elif 'Name:' in each:
                                update['serverName'] = each.split(':')[1].strip().decode('utf-8', 'replace')  # store in utf-8
                            elif 'Port:' in each:
                                update['port'] = each.split(':')[1].strip()
                            elif 'Updated-At:' in each:
                                update['updated'] = each.split(':')[1].strip()
                            elif 'Version:' in each:
                                update['version'] = each.split(':')[1].strip()
                    PMS_list.append(update)

            if len(PMS_list) == 0:
                self.logger.info('GDM: No servers discovered')
            else:
                self.logger.info('GDM: Servers discovered: %s' % str(len(PMS_list)))

            for server in PMS_list:
                if server['uuid'] == id:
                    return {'servers': server}

            return {'servers': PMS_list}

        except Exception as e:
            self.logger.debug('Exception: %s' % e)
            self.logger.error('Unable to get players')
            return 'error'

    @cherrypy.expose()
    @require()
    @cherrypy.tools.json_out()
    def PlayItem(self, playerip, machineid, item=None, type=None, offset=0, **kwargs):
        ''' Play a file in Plex '''
        self.logger.debug('Playing %s on %s type %s offset %s' % (item, playerip, type, offset))
        # Ripped a lot for plexapi so all credits goes there, the parameters are very picky...
        # The maybe swich to the api?
        try:
            plex_host = htpc.settings.get('plex_host', '')
            plex_port = htpc.settings.get('plex_port', '32400')
            # urllib2 sucks should use requests
            data = {'shuffle': 0,
                    'continuous': 0,
                    'type': 'video'}

            data['X-Plex-Client-Identifier'] = str(hex(getnode()))
            data['uri'] = 'library://__GID__/item//library/metadata/%s' % item
            data['key'] = '/library/metadata/%s' % item
            path = 'playQueues%s' % joinArgs(data)

            quecommand = "http://%s:%s/%s" % (plex_host, plex_port, path)
            x = requests.post(quecommand, headers=self.getHeaders())
            # So we have qued the video, lets find it playQueueID
            find_playerq = x.json()
            playerq = find_playerq.get('playQueueID')
            # Need machineIdentifier
            s = self.JsonLoader(urlopen(Request('http://%s:%s/' % (plex_host, plex_port), headers=self.getHeaders())).read())

            b_url = 'http://%s:%s/system/players/%s/' % (plex_host, plex_port, playerip)

            ctkey = '/playQueues/%s?window=100&own=1' % playerq
            arg = {'machineIdentifier': s.get('machineIdentifier'),
                   'key': '/library/metadata/' + item,
                   'containerKey': ctkey,
                   'offset': 0
                   }
            play = 'playback/playMedia%s' % joinArgs(arg)
            playcommand = b_url + play
            r = requests.get(playcommand, headers=self.getHeaders())
            self.logger.debug("playcommand is %s" % playcommand)

        except Exception as e:
            self.logger.debug('Exception: %s' % e)
            self.logger.error('Unable to play %s on player %s type %s offset %s' % (item, playerip, type, offset))
            return 'error'

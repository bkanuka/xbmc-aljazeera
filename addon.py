#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright 2011 Jonathan Beluch.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from xbmcswift import Plugin, download_page, xbmc, xbmcgui
from xbmcswift.ext.playlist import playlist
from BeautifulSoup import BeautifulSoup as BS
from urllib import urlencode
from urlparse import urljoin
import re
try:
    import json
except ImportError:
    import simplejson as json


PLUGIN_NAME = 'AlJazeera'
PLUGIN_ID = 'plugin.video.aljazeera'


plugin = Plugin(PLUGIN_NAME, PLUGIN_ID, __file__)
plugin.register_module(playlist, url_prefix='/_playlist')


BASE_URL = 'http://english.aljazeera.net'
def full_url(path):
    return urljoin(BASE_URL, path)

def extract_videoid(url):
    return url.split("/")[-1:][0]

YOUTUBE_PTN = 'plugin://plugin.video.youtube/?action=play_video&videoid=%s'
def youtube_url(videoid):
    return YOUTUBE_PTN % (videoid)

def parse_video(video):
    '''Returns a dict of information for a given json video object.'''
    
    info = {
        'title': video['title']['$t'],
        'summary': video['media$group']['media$description']['$t'],
        'videoid': extract_videoid(video['id']['$t']),
    }
    info['thumbnail'] = "http://i.ytimg.com/vi/" + info['videoid'] + "/0.jpg"
    
    # TODO
    # Make a datetime
    #info['published'] = video['published']['$t']
    return info


def get_videos(query, start_index = 1):
    '''Returns a tuple of (videos, total_videos) where videos is a list of
    dicts containing video information and total_videos is the toal number
    of videos available for the given query. The number of videos returned
    is specified by the given count.'''

    url_ptn = 'http://gdata.youtube.com/feeds/api/videos/?%s'
    
    params = {
        'q': query,
        'author': 'AlJazeeraEnglish',
        'alt': 'json',  # Ask YT to return JSON
        'max-results': '12',
        'start-index': str(start_index),
        'orderby': 'published',
        'prettyprint': 'true',  # Makes debugging easier
    }
    
    url = url_ptn % urlencode(params)
    print url
    
    src = download_page(url)
    resp = json.loads(src)
    
    try:
        videos = resp['feed']['entry']
    except:
        video_infos = []
        total_results = 0
        return videos_info, total_results
    
    video_infos = map(parse_video, videos)
    total_results = int(resp['feed']['openSearch$totalResults']['$t'])
    
    return video_infos, total_results


@plugin.route('/', default=True)
def show_homepage():
    items = [
        # Watch Live
        {'label': plugin.get_string(30100),
         'url': plugin.url_for('watch_live')},
        # Watch Live
        {'label': plugin.get_string(30100) + " HD",
         'url': plugin.url_for('watch_live_hd')},
        # Programs
        {'label': plugin.get_string(30102),
         'url': plugin.url_for('show_programs')},
        # News Clips
        {'label': plugin.get_string(30101),
         'url': plugin.url_for('show_all_clips')},
    ]
    return plugin.add_items(items)


@plugin.route('/live/')
def watch_live():
    rtmpurl = 'rtmp://aljazeeraflashlivefs.fplive.net:1935/aljazeeraflashlive-live/aljazeera_eng_med live=true'
    li = xbmcgui.ListItem('AlJazeera Live')
    xbmc.Player(xbmc.PLAYER_CORE_DVDPLAYER).play(rtmpurl, li)
    # Return an empty list so we can test with plugin.crawl() and
    # plugin.interactive()
    return []


@plugin.route('/live_hd/')
def watch_live_hd():
    rtmpurl = 'rtmp://aljazeeraflashlivefs.fplive.net:1935/aljazeeraflashlive-live/aljazeera_eng_high live=true'
    li = xbmcgui.ListItem('AlJazeera HD Live')
    xbmc.Player(xbmc.PLAYER_CORE_DVDPLAYER).play(rtmpurl, li)
    # Return an empty list so we can test with plugin.crawl() and
    # plugin.interactive()
    return []


@plugin.route('/programs/')
def show_programs():
    '''Shows categories available for either Clips or Programs on the aljazeera
    video page.
    '''
    url = full_url('video')
    src = download_page(url)
    # Fix shitty HTML so BeautifulSoup doesn't break
    src = src.replace('id"adSpacer"', 'id="adSpacer"')
    html = BS(src)

    tds = html.findAll('td', {
        'id': re.compile('^mItem_'),
        'onclick': re.compile(r"""SelectProgInfo(?!\('Selected'\))""")  # programs
        # 'onclick': re.compile(r"""SelectProgInfo\('Selected'\)""")    # news clips
    })

    items = []

    for td in tds:
        query = td.string
        items.append({
            'label': td.string,
            'url': plugin.url_for('show_videos', query = query, start_index = '1')
        })

    # TODO: Add images
    return plugin.add_items(items)


@plugin.route('/all/')
def show_all_clips():
    pass


@plugin.route('/videos/<query>/<start_index>/')
def show_videos(query = None, start_index = '1'):
    '''List videos available for a given category. Only 13 videos are displayed
    at a time. If there are older or newer videos, appropriate list items will
    be placed at the top of the list.
    '''
    start_index = int(start_index)

    videos, total_results = get_videos(query, start_index)
    
    items = [{
        'label': video['title'],
        'thumbnail': video['thumbnail'],
        'info': {'plot': video['summary'], },
        'url': youtube_url(video['videoid']),
        'is_folder': False,
        'is_playable': True,
        'context_menu': [(
            #'Add to Now Playing'
            plugin.get_string(30300),
            'XBMC.RunPlugin(%s)' % plugin.url_for(
                'playlist.add_to_playlist',
                url=youtube_url(video['videoid']),
                label=video['title']
            )
        )],
    } for video in videos]

    # Add '> Older' and '< Newer' list items if the list spans more than 1 page
    # (e.g. > 13 videos)
    if start_index + 12 < total_results:
        items.append({
            # More videos
            'label': u'%s »' % plugin.get_string(30200),
            'url': plugin.url_for('show_videos', query = query,
                                  start_index = str(start_index + 12))
        })
    #if int(start_index) > 1:
    #    items.insert(0, {
    #        # Newer videos
    #        'label': u'« %s' % plugin.get_string(30201),
    #        'url': plugin.url_for('show_videos', count=count, list_id=list_id,
    #                              start_index=str(int(start_index) - int(count))),
    #    })

    return plugin.add_items(items)


if __name__ == '__main__':
    plugin.run()

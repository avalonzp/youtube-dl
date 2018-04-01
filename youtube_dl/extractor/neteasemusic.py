# coding: utf-8
from __future__ import unicode_literals

from hashlib import md5
from base64 import b64encode
from datetime import datetime
import re
import random
import json

from ..aes import (
    aes_cbc_decrypt,
    aes_cbc_encrypt,
)
from .common import InfoExtractor
from ..compat import (
    compat_urllib_parse_urlencode,
    compat_str,
    compat_itertools_count,
)
from ..utils import (
    sanitized_Request,
    float_or_none,
    ohdave_rsa_encrypt,
    bytes_to_intlist as b2l,
    intlist_to_bytes as l2b,
)


class NetEaseMusicBaseIE(InfoExtractor):
    _FORMATS = ['b', 'm', 'h', 'bMusic', 'mMusic', 'hMusic']
    _NETEASE_SALT = '3go8&$8*3*3h0k(2)2'
    _API_BASE = 'http://music.163.com/'
    _NONCE_ = b'0CoJUm6Qyw8W8jud'
    _MODULUS_ = 0x00e0b509f6259df8642dbc35662901477df22677ec152b5ff68ace615bb7b725152b3ab17a876aea8a5aa76d2e417629ec4ee341f56135fccf695280104e0312ecbda92557c93870114af6c9d05c4f7f0c3685b7a46bee255932575cce10b424d813cfe4875d3e82047b97ddef52741d546b8e289dc6935b3ece0462db0a22b8e7
    _PUBKEY_ = 0x010001
    _AGENTS_ = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1",
        "Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 5.1.1; Nexus 6 Build/LYZ28E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_2 like Mac OS X) AppleWebKit/603.2.4 (KHTML, like Gecko) Mobile/14F89;GameHelper",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/603.2.4 (KHTML, like Gecko) Version/10.1.1 Safari/603.2.4",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 10_0 like Mac OS X) AppleWebKit/602.1.38 (KHTML, like Gecko) Version/10.0 Mobile/14A300 Safari/602.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:46.0) Gecko/20100101 Firefox/46.0", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:46.0) Gecko/20100101 Firefox/46.0",
        "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)", "Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0)", "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0)",
        "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Win64; x64; Trident/6.0)", "Mozilla/5.0 (Windows NT 6.3; Win64, x64; Trident/7.0; rv:11.0) like Gecko",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/13.10586",
        "Mozilla/5.0 (iPad; CPU OS 10_0 like Mac OS X) AppleWebKit/602.1.38 (KHTML, like Gecko) Version/10.0 Mobile/14A300 Safari/602.1"
    ]

    @classmethod
    def _encrypt(cls, dfsid):
        salt_bytes = bytearray(cls._NETEASE_SALT.encode('utf-8'))
        string_bytes = bytearray(compat_str(dfsid).encode('ascii'))
        salt_len = len(salt_bytes)
        for i in range(len(string_bytes)):
            string_bytes[i] = string_bytes[i] ^ salt_bytes[i % salt_len]
        m = md5()
        m.update(bytes(string_bytes))
        result = b64encode(m.digest()).decode('ascii')
        return result.replace('/', '_').replace('+', '-')

    def extract_formats(self, info):
        formats = []
        for song_format in self._FORMATS:
            details = info.get(song_format)
            if not details:
                continue

            params = {'ids': [str(info['id'])], 'br': int(details.get('br', details.get('bitrate', 128000))), 'csrf_token': ''}
            url_info = self.query_api('weapi/song/enhance/player/url', params, info['id'], 'Fetching song url')['data'][0]
            url = url_info.get('url', None)

            if url:
                if self._is_valid_url(url, info['id'], 'song'):
                    formats.append({
                        'url': url,
                        'ext': url_info.get('type'),
                        'abr': float_or_none(url_info.get('br'), scale=1000),
                        'format_id': song_format,
                        'filesize': url_info.get('size'),
                    })
                    break
        return formats

    @classmethod
    def convert_milliseconds(cls, ms):
        return int(round(ms / 1000.0))

    @classmethod
    def create_secretkey(cls, size):
        keys = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        return ''.join(list(keys[int(random.random() * len(keys))] for x in range(size)))

    def aes_crypt(self, params):
        plain_text = bytes(json.dumps(params, ensure_ascii=True).replace(' ', ''), 'utf-8')
        if len(plain_text) % 16 == 0:
            plain_text = plain_text + bytes([0x10] * 16)

        sec_key = bytes(self.create_secretkey(16), 'utf-8')
        lv = b'0102030405060708'
        part_one = b64encode(l2b(aes_cbc_encrypt(b2l(plain_text), b2l(self._NONCE_), lv)))

        if len(part_one) % 16 == 0:
            part_one = part_one + bytes([0x10] * 16)
        enc_text = b64encode(l2b(aes_cbc_encrypt(b2l(part_one), b2l(sec_key), lv)))

        enc_seckey = ohdave_rsa_encrypt(sec_key, self._PUBKEY_, self._MODULUS_)
        return {'params': enc_text, 'encSecKey': enc_seckey}

    def query_api(self, endpoint, params, video_id, note):
        req = sanitized_Request('%s%s' % (self._API_BASE, endpoint))
        for key, value in {
                'Referer': self._API_BASE,
                'Accept': '*/*',
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': random.choice(self._AGENTS_),
        }.items():
            req.add_header(key, value)
        self.to_screen(params)
        req.method = 'POST'
        req.data = compat_urllib_parse_urlencode(self.aes_crypt(params))
        return self._download_json(req, video_id, note)


class NetEaseMusicIE(NetEaseMusicBaseIE):
    IE_NAME = 'netease:song'
    IE_DESC = '网易云音乐'
    _VALID_URL = r'https?://music\.163\.com/(#/)?song\?id=(?P<id>[0-9]+)'
    _TESTS = [{
        'note': 'No lyrics translation.',
        'url': 'http://music.163.com/#/song?id=29822014',
        'info_dict': {
            'id': '29822014',
            'ext': 'mp3',
            'title': '听见下雨的声音',
            'creator': '周杰伦',
            'upload_date': '20141225',
            'timestamp': 1419523200,
            'description': 'md5:a4d8d89f44656af206b7b2555c0bce6c',
        },
        'skip': 'VIP required'
    }, {
        'note': 'No lyrics.',
        'url': 'http://music.163.com/song?id=17241424',
        'info_dict': {
            'id': '17241424',
            'ext': 'mp3',
            'title': 'Opus 28',
            'creator': 'Dustin O\'Halloran',
            'upload_date': '20080211',
            'timestamp': 1202745600,
        },
        'skip': 'Blocked outside Mainland China',
    }, {
        'note': 'Has translated name.',
        'url': 'http://music.163.com/#/song?id=22735043',
        'info_dict': {
            'id': '22735043',
            'ext': 'mp3',
            'title': '소원을 말해봐 (Genie)',
            'creator': '少女时代',
            'description': 'md5:79d99cc560e4ca97e0c4d86800ee4184',
            'upload_date': '20100127',
            'timestamp': 1264608000,
            'alt_title': '说出愿望吧(Genie)',
        },
        'skip': 'Blocked outside Mainland China',
    }]

    def _process_lyrics(self, lyrics_info):
        original = lyrics_info.get('lrc', {}).get('lyric')
        translated = lyrics_info.get('tlyric', {}).get('lyric')

        if not translated:
            return original

        lyrics_expr = r'(\[[0-9]{2}:[0-9]{2}\.[0-9]{2,}\])([^\n]+)'
        original_ts_texts = re.findall(lyrics_expr, original)
        translation_ts_dict = dict((time_stamp, text) for time_stamp, text in re.findall(lyrics_expr, translated))
        lyrics = '\n'.join(['%s%s / %s' % (time_stamp, text, translation_ts_dict.get(time_stamp, '')) for time_stamp, text in original_ts_texts])
        return lyrics

    def _real_extract(self, url):
        song_id = self._match_id(url)

        params = {'c': json.dumps([{'id': int(song_id)}]), 'ids': '[%s]' % song_id, 'csrf_token': ''}
        info = self.query_api('weapi/v3/song/detail', params, song_id, 'Downloading song info')['songs'][0]

        formats = self.extract_formats(info)
        self._sort_formats(formats)

        lyrics_info = self.query_api('weapi/song/lyric?os=osx&id=%s&lv=-1&tv=-1&kv=-1' % song_id, {}, song_id, 'Downloading lyrics data')
        lyrics = self._process_lyrics(lyrics_info)

        alt_title = None
        if info.get('tns'):
            alt_title = '/'.join(info.get('tns'))

        return {
            'id': song_id,
            'title': info['name'],
            'alt_title': alt_title,
            'creator': ' / '.join([artist['name'] for artist in info.get('ar', [])]),
            'timestamp': self.convert_milliseconds(info.get('publishTime')),
            'thumbnail': info.get('al', {}).get('picUrl'),
            'duration': self.convert_milliseconds(info.get('dt', 0)),
            'description': lyrics,
            'formats': formats,
        }


class NetEaseMusicAlbumIE(NetEaseMusicBaseIE):
    IE_NAME = 'netease:album'
    IE_DESC = '网易云音乐 - 专辑'
    _VALID_URL = r'https?://music\.163\.com/(#/)?album\?id=(?P<id>[0-9]+)'
    _TEST = {
        'url': 'http://music.163.com/#/album?id=220780',
        'info_dict': {
            'id': '220780',
            'title': 'B\'day',
            'description': 'Japanese pressing of 2006 album features 15 tracks including bonus international versions, 2 hidden tracks and the Japan only track \'Creole\'. Sony.\n\n'
        },
        'playlist_count': 23,
        'skip': 'Blocked outside Mainland China',
    }

    def _real_extract(self, url):
        album_id = self._match_id(url)

        params = {'csrf_token': ''}
        info = self.query_api('weapi/v1/album/%s' % album_id, params, album_id, 'Downloading album data')

        name = info['album']['name']
        desc = info['album']['description']
        entries = [self.url_result('http://music.163.com/#/song?id=%s' % song['id'], 'NetEaseMusic', song['id']) for song in info['songs']]

        return self.playlist_result(entries, album_id, name, desc)


class NetEaseMusicSingerIE(NetEaseMusicBaseIE):
    IE_NAME = 'netease:singer'
    IE_DESC = '网易云音乐 - 歌手'
    _VALID_URL = r'https?://music\.163\.com/(#/)?artist\?id=(?P<id>[0-9]+)'
    _TESTS = [{
        'note': 'Singer has aliases.',
        'url': 'http://music.163.com/#/artist?id=10559',
        'info_dict': {
            'id': '10559',
            'title': '张惠妹 - aMEI;阿密特',
        },
        'playlist_count': 50,
        'skip': 'Blocked outside Mainland China',
    }, {
        'note': 'Singer has translated name.',
        'url': 'http://music.163.com/#/artist?id=124098',
        'info_dict': {
            'id': '124098',
            'title': '李昇基 - 이승기',
        },
        'playlist_count': 50,
        'skip': 'Blocked outside Mainland China',
    }]

    def _real_extract(self, url):
        singer_id = self._match_id(url)

        params = {'csrf_token': ''}

        info = self.query_api('weapi/v1/artist/%s' % singer_id, params, singer_id, 'Downloading singer data')

        name = info['artist']['name']
        if info['artist']['trans']:
            name = '%s - %s' % (name, info['artist']['trans'])
        if info['artist']['alias']:
            name = '%s - %s' % (name, ';'.join(info['artist']['alias']))

        entries = [self.url_result('http://music.163.com/#/song?id=%s' % song['id'], 'NetEaseMusic', song['id']) for song in info['hotSongs']]
        return self.playlist_result(entries, singer_id, name)


class NetEaseMusicListIE(NetEaseMusicBaseIE):
    IE_NAME = 'netease:playlist'
    IE_DESC = '网易云音乐 - 歌单'
    _VALID_URL = r'https?://music\.163\.com/(#/)?(playlist|discover/toplist)\?id=(?P<id>[0-9]+)'
    _TESTS = [{
        'url': 'http://music.163.com/#/playlist?id=79177352',
        'info_dict': {
            'id': '79177352',
            'title': 'Billboard 2007 Top 100',
            'description': 'md5:12fd0819cab2965b9583ace0f8b7b022'
        },
        'playlist_count': 97,
        'skip': 'Blocked outside Mainland China',
    }, {
        'note': 'Toplist/Charts sample',
        'url': 'http://music.163.com/#/discover/toplist?id=3733003',
        'info_dict': {
            'id': '3733003',
            'title': 're:韩国Melon排行榜周榜 [0-9]{4}-[0-9]{2}-[0-9]{2}',
            'description': 'md5:73ec782a612711cadc7872d9c1e134fc',
        },
        'playlist_count': 50,
        'skip': 'Blocked outside Mainland China',
    }]

    def _real_extract(self, url):
        list_id = self._match_id(url)

        params = {'id': str(list_id), 'n': 100000, 'csrf_token': ''}

        info = self.query_api('api/playlist/detail?id=%s' % list_id, params, list_id, 'Downloading playlist data')['result']

        name = info['name']
        desc = info.get('description')

        if info.get('specialType') == 10:  # is a chart/toplist
            datestamp = datetime.fromtimestamp(self.convert_milliseconds(info['updateTime'])).strftime('%Y-%m-%d')
            name = '%s %s' % (name, datestamp)

        entries = [self.url_result('http://music.163.com/#/song?id=%s' % song['id'], 'NetEaseMusic', song['id']) for song in info['tracks']]
        return self.playlist_result(entries, list_id, name, desc)


class NetEaseMusicMvIE(NetEaseMusicBaseIE):
    IE_NAME = 'netease:mv'
    IE_DESC = '网易云音乐 - MV'
    _VALID_URL = r'https?://music\.163\.com/(#/)?mv\?id=(?P<id>[0-9]+)'
    _TEST = {
        'url': 'http://music.163.com/#/mv?id=415350',
        'info_dict': {
            'id': '415350',
            'ext': 'mp4',
            'title': '이럴거면 그러지말지',
            'description': '白雅言自作曲唱甜蜜爱情',
            'creator': '白娥娟',
            'upload_date': '20150520',
        },
        'skip': 'Blocked outside Mainland China',
    }

    def _real_extract(self, url):
        mv_id = self._match_id(url)

        params = {
            'id': str(mv_id),
        }

        info = self.query_api('weapi/mv/detail', params, mv_id, 'Downloading mv info')['data']

        formats = [{'url': mv_url, 'ext': 'mp4', 'format_id': '%sp' % brs, 'height': int(brs)} for brs, mv_url in info['brs'].items()]
        self._sort_formats(formats)

        return {
            'id': mv_id,
            'title': info['name'],
            'description': info.get('desc') or info.get('briefDesc'),
            'creator': info['artistName'],
            'upload_date': info['publishTime'].replace('-', ''),
            'formats': formats,
            'thumbnail': info.get('cover'),
            'duration': self.convert_milliseconds(info.get('duration', 0)),
        }


class NetEaseMusicProgramIE(NetEaseMusicBaseIE):
    IE_NAME = 'netease:program'
    IE_DESC = '网易云音乐 - 电台节目'
    _VALID_URL = r'https?://music\.163\.com/(#/?)program\?id=(?P<id>[0-9]+)'
    _TESTS = [{
        'url': 'http://music.163.com/#/program?id=10109055',
        'info_dict': {
            'id': '10109055',
            'ext': 'mp3',
            'title': '不丹足球背后的故事',
            'description': '喜马拉雅人的足球梦 ...',
            'creator': '大话西藏',
            'timestamp': 1434179342,
            'upload_date': '20150613',
            'duration': 900,
        },
        'skip': 'Blocked outside Mainland China',
    }, {
        'note': 'This program has accompanying songs.',
        'url': 'http://music.163.com/#/program?id=10141022',
        'info_dict': {
            'id': '10141022',
            'title': '25岁，你是自在如风的少年<27°C>',
            'description': 'md5:8d594db46cc3e6509107ede70a4aaa3b',
        },
        'playlist_count': 4,
        'skip': 'Blocked outside Mainland China',
    }, {
        'note': 'This program has accompanying songs.',
        'url': 'http://music.163.com/#/program?id=10141022',
        'info_dict': {
            'id': '10141022',
            'ext': 'mp3',
            'title': '25岁，你是自在如风的少年<27°C>',
            'description': 'md5:8d594db46cc3e6509107ede70a4aaa3b',
            'timestamp': 1434450841,
            'upload_date': '20150616',
        },
        'params': {
            'noplaylist': True
        },
        'skip': 'Blocked outside Mainland China',
    }]

    def _real_extract(self, url):
        program_id = self._match_id(url)

        info = self.query_api('dj/program/detail?id=%s' % program_id, program_id, 'Downloading program info')['program']

        name = info['name']
        description = info['description']

        if not info['songs'] or self._downloader.params.get('noplaylist'):
            if info['songs']:
                self.to_screen('Downloading just the main audio %s because of --no-playlist' % info['mainSong']['id'])

            formats = self.extract_formats(info['mainSong'])
            self._sort_formats(formats)

            return {
                'id': program_id,
                'title': name,
                'description': description,
                'creator': info['dj']['brand'],
                'timestamp': self.convert_milliseconds(info['createTime']),
                'thumbnail': info['coverUrl'],
                'duration': self.convert_milliseconds(info.get('duration', 0)),
                'formats': formats,
            }

        self.to_screen('Downloading playlist %s - add --no-playlist to just download the main audio %s' % (program_id, info['mainSong']['id']))

        song_ids = [info['mainSong']['id']]
        song_ids.extend([song['id'] for song in info['songs']])
        entries = [self.url_result('http://music.163.com/#/song?id=%s' % song_id, 'NetEaseMusic', song_id) for song_id in song_ids]
        return self.playlist_result(entries, program_id, name, description)


class NetEaseMusicDjRadioIE(NetEaseMusicBaseIE):
    IE_NAME = 'netease:djradio'
    IE_DESC = '网易云音乐 - 电台'
    _VALID_URL = r'https?://music\.163\.com/(#/)?djradio\?id=(?P<id>[0-9]+)'
    _TEST = {
        'url': 'http://music.163.com/#/djradio?id=42',
        'info_dict': {
            'id': '42',
            'title': '声音蔓延',
            'description': 'md5:766220985cbd16fdd552f64c578a6b15'
        },
        'playlist_mincount': 40,
        'skip': 'Blocked outside Mainland China',
    }
    _PAGE_SIZE = 1000

    def _real_extract(self, url):
        dj_id = self._match_id(url)

        params = {'radioId': str(dj_id), 'csrf_token': '', 'asc': None, 'limit': None, 'offset': None}

        entries = []
        for offset in compat_itertools_count(start=0, step=self._PAGE_SIZE):
            info = self.query_api('weapi/dj/program/byradio', params, dj_id, 'Downloading dj programs - %d' % offset)

            entries.extend([self.url_result('http://music.163.com/#/program?id=%s' % program['id'], 'NetEaseMusicProgram', program['']) for program in info['programs']])

            if name is None:
                radio = info['programs'][0]['radio']
                name = radio['name']
                desc = radio['desc']

            if not info['more']:
                break

        return self.playlist_result(entries, dj_id, name, desc)

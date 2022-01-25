import os
import sys

import requests

from log import log


def qbt_upload_torrent_file(root_url, username, pwd, torrent_filename,
                            category, remove_torrent_file: bool):
    try:
        headers = {'Referer': root_url}
        login_data = {'username': username, 'password': pwd}

        login_url = '{}/api/v2/auth/login'.format(root_url)

        resp = requests.post(login_url, data=login_data, headers=headers)
        log.debug('qbt login result code: {}'.format(resp.status_code))
        cookie = []
        if resp.status_code == 200:
            log.debug('resp Set-Cookie={}'.format(resp.headers['Set-Cookie']))
            cookie = resp.headers['Set-Cookie'].split('=')
        else:
            log.error('qbt login failed, code:{}, test:{}'.format(
                resp.status_code, resp.text))
            return False

        cookies = {cookie[0]: cookie[1]}
        # app_version_url = '{}/api/v2/app/webapiVersion'.format(root_url)
        # resp = requests.get(app_version_url, headers, cookies=cookies)
        # if resp.status_code != 200:
        #     log.error('get api version failed, code:{}'.format(resp.status_code))
        #     return False
        # log.debug('api versino:{}'.format(resp.text))

        #torrent_filename = 'dcab2e60e3.torrent'
        new_torrent_url = '{}/api/v2/torrents/add'.format(root_url)
        files = {
            'torrents':
            (torrent_filename, open(torrent_filename,
                                    'rb'), 'application/x-bittorrent')
        }
        files_data = {
            'category': category,
            'autoTMM': True,
        }

        resp = requests.post(new_torrent_url,
                             data=files_data,
                             headers=headers,
                             cookies=cookies,
                             files=files)
        if resp.status_code != 200:
            log.error('new torrent failed, code:{}'.format(resp.status_code))
            return False
        log.info('torrent: {} resp: {}'.format(torrent_filename, resp.text))

        if remove_torrent_file:
            os.remove(torrent_filename)
    except Exception as ex:
        log.error('qbt upload torrent file failed, %s', type(ex))
        return False

    return True

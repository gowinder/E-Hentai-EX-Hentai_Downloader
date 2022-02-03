import base64
import json
import logging
import os
import re
import shutil
import zipfile
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

import progressbar
import qbittorrentapi
import requests
from dotenv import dotenv_values
from pyaria2 import Aria2RPC

from log import log

env_config = dotenv_values()

PROXY_POOL_ADDR = env_config.get('PROXY_POOL_ADDR')
log.info('PROXY_POOL_ADDR: %s' % PROXY_POOL_ADDR)


def get_proxy_from_pool():
    if not PROXY_POOL_ADDR:
        return None

    return requests.get("{}get/".format(PROXY_POOL_ADDR)).json()


def delete_proxy_from_pool(proxy):
    if not PROXY_POOL_ADDR:
        return
    requests.get("{}delete/?proxy={}".format(PROXY_POOL_ADDR, proxy))


def get_requests_proxies():
    proxies = {}
    ret = get_proxy_from_pool()
    if not ret:
        log.info('No proxy from proxy pool')
        return proxies
    proxies['http'] = 'http://{}'.format(ret['proxy'])
    proxies['https'] = 'http://{}'.format(ret['proxy'])
    log.info('Get proxy from proxy pool: %s' % ret['proxy'])
    return proxies


def get_zip_filename_by_dir(folder_path):
    zip_filename = "%s.zip" % folder_path
    return zip_filename


def make_zip(folder_path, remove=True):
    zip_filename = get_zip_filename_by_dir(folder_path)
    if os.path.exists(zip_filename):
        return zip_filename
    with zipfile.ZipFile(zip_filename, 'w', allowZip64=True) as zipFile:
        for f in sorted(os.listdir(folder_path)):
            fullpath = os.path.join(folder_path, f)
            zipFile.write(fullpath, f, zipfile.ZIP_STORED)
    if remove:
        shutil.rmtree(folder_path)
    return zip_filename


def send_qbt_task(torrent_file):
    logging.getLogger('qbittorrentapi').setLevel(logging.DEBUG)

    qbt_client = qbittorrentapi.Client(
        host=env_config['QBT_HOST'],
        port=int(env_config['QBT_PORT']),
        username=env_config['QBT_USERNAME'],
        password=env_config['QBT_PWD'],
        RAISE_NOTIMPLEMENTEDERROR_FOR_UNIMPLEMENTED_API_ENDPOINTS=True)

    try:
        qbt_client.auth_log_in()
        # log.info('qbt version: {}'.format(qbt_client.app_version()))
        # log.info('qbt torrents info: {}'.format(qbt_client.torrents_info()))
    except qbittorrentapi.LoginFailed as e:
        log.error('qbittorrent login failed, %s', type(e))

    category = env_config['QBT_CATEGORY']
    if qbt_client.torrents_add(torrent_file=torrent_file,
                               category=category,
                               use_auto_torrent_management=True,
                               is_paused=False):
        log.info('qbittorrent add task [%s] success' % (category))
        return True
    else:
        log.info('qbittorrent add task [%s] failed' % (category))
        return False


def send_aria_torrent_task(torrent_content):
    torrent = base64.b64encode(torrent_content).decode('utf-8')
    token = 'token:{}'.format(env_config['ARIA_RPC_SECRET'])
    dir = 'dir:{}'.format(env_config['ARIA_DOWN_DIR'])
    jsonreq = json.dumps({
        'jsonrpc': '2.0',
        'id': 'qbt_api',
        'method': 'aria2.addTorrent',
        'params': [token, torrent],
    })

    ret = requests.post(env_config['ARIA_RPC_ADDRESS'], jsonreq)
    log.info('aria2 add task ret: %s' % ret)
    return ret


def send_aria_download_task(title, url, path):
    token = 'token:{}'.format(env_config['ARIA_RPC_SECRET'])
    jsonreq = json.dumps({
        'jsonrpc': '2.0',
        'id': 'qbt_api',
        'method': 'aria2.addUri',
        'params': [token, [url], {
            'dir': path
        }],
    })

    ret = requests.post(env_config['ARIA_RPC_ADDRESS'], jsonreq)
    if ret.status_code == 200:
        log.info('send aria download {} success'.format(title))
        return True
    else:
        log.info('send aria download {} failed, status code: {}'.format(
            title, ret.status_code))
        return False


def get_numbers_from_text(text: str) -> list:
    '''
    ref: https://stackoverflow.com/questions/4289331/how-to-extract-numbers-from-a-string-in-python
    '''
    return [int(s) for s in text.split() if s.isdigit()]


def get_ban_time_from_text(text: str) -> timedelta:
    numbers = get_numbers_from_text(text)

    if len(numbers) == 1:
        return timedelta(seconds=numbers[0])
    if len(numbers) == 2:
        return timedelta(seconds=numbers[1], minutes=numbers[0])
    if len(numbers) == 3:
        return timedelta(seconds=numbers[2],
                         minutes=numbers[1],
                         hours=numbers[0])
    if len(numbers) == 4:
        return timedelta(seconds=numbers[3],
                         minutes=numbers[2],
                         hours=numbers[1],
                         days=numbers[0])
    return timedelta(seconds=0)


def get_archive_download_form(soup):
    form_list = soup.find_all('form')
    res_form = org_form = None
    for form in form_list:
        if form.input['value'] == 'res':
            log.debug('download_archive, get archive res form address: %s',
                      form.action)
            res_form = form
        elif form.input['value'] == 'org':
            log.debug('download_archive, get archive org form address: %s',
                      form.action)
            org_form = form

    return org_form, res_form


def replace_url_path(url: str, new_path: str) -> str:
    path = urlsplit(url)
    new_path = path._replace(path=new_path)
    new_url = urlunsplit(new_path)
    return new_url


def tag_to_path(tag: str) -> str:
    return tag.replace('/', '_')


def download_file(filename, url, cookies):
    try:
        with requests.get(url, stream=True, cookies=cookies) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            if os.path.isfile(filename):
                if os.path.getsize(filename) != total_size:
                    log.info(
                        '{} already exists, but size not match, remove to redownload'
                        .format(filename))
                    os.remove(filename)
                else:
                    log.info('{} already exists, skip'.format(filename))
                    return True
            with progressbar.ProgressBar(max_value=total_size) as bar:
                with open(filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        bar.update(bar.value + len(chunk))
    except Exception as ex:
        log.error('download_file failed, file:{}, url:{}, exception:{}'.format(
            filename, url, type(ex)))
        return False
    log.info('{} download completed'.format(filename))
    return True


def filter_tag(tag_str: str) -> str:
    return re.sub('[^a-zA-Z0-9 \n\.]', '_', tag_str)
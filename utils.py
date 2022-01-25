import base64
import json
import logging
import os
import shutil
import zipfile

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


def send_aria_task(torrent_content):
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

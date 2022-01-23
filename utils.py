import os
import shutil
import zipfile
from logging import StreamHandler
from turtle import dot

import requests
from charset_normalizer import logging
from dotenv import dotenv_values

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

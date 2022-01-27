# -*- coding: utf-8 -*-
import asyncio
import multiprocessing
import os
import re
import time
import urllib
from datetime import datetime
from distutils import archive_util

import aiofiles
import httpx
import progressbar
import redis
import requests
#from _overlapped import NULL
from bs4 import BeautifulSoup
from dotenv import dotenv_values
from lxml import etree
from redis import Redis

from log import log
from qbt_torrent import qbt_upload_torrent_file
from utils import (download_file, get_archive_download_form,
                   get_ban_time_from_text, get_requests_proxies,
                   get_zip_filename_by_dir, make_zip, replace_url_path,
                   send_aria_download_task, send_aria_torrent_task,
                   send_qbt_task, tag_to_path)
from version import VERSION

env_config = dotenv_values()

DOWNLOADED_URL_REDIS_KEY = 'crawler:url:downloaded'
QUEUED_URL_REDIS_KEY = 'crawler:url:queued'
DOWNLOADING_URL_REDIS_KEY = 'crawler:url:downloading'
FAILED_URL_REDIS_KEY = 'crawler:url:failed'
TORRENT_URL_REDIS_KEY = 'crawler:torrent:url'
SKIPPED_URL_REDIS_KEY = 'crawler:skipped:url'
redis_conn = Redis.from_url(env_config['REDIS_URL'])
MAX_RETRY = int(env_config['MAX_RETRY'])

proxies = get_requests_proxies()

total_download = 0

NULL = None
headers = {
    'User-Agent':
    'Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.82 '
    'Safari/537.36',
    'Accept':
    'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Upgrade-Insecure-Requests':
    '1'
}


def download_archive(soup, cookies2, spath, original_tag):
    global total_download
    g2s_gsp_list = soup.find_all(class_='g2 gsp')
    for g2_gsp in g2s_gsp_list:
        onclick = g2_gsp.a['onclick']
        if onclick and onclick.find('archiver.php') != -1:
            log.debug('download_archive, onclick:%s', onclick)
            p = re.compile(".+?\'(.+?)\'")
            ret = p.findall(onclick)
            if len(ret) > 0 and ret[0].startswith(
                    'https://exhentai.org/archiver.php'):
                log.debug('download_archive, get archive page address: %s',
                          ret[0])

                response = requests.get(
                    ret[0],
                    headers=headers,
                    cookies=cookies2,
                )
                content = response.text
                soup = BeautifulSoup(content, 'lxml')
                org_form, res_form = get_archive_download_form(soup)
                selected_form = res_form
                if env_config['ENABLE_DOWNLOAD_ARCHIVE_RESAMPLED'] == 'false':
                    selected_form = org_form

                form_headers = headers
                form_headers[
                    'Content-Type'] = 'application/x-www-form-urlencoded'
                form_headers['Referer'] = ret[0]
                form_data = {
                    'dltype': selected_form.input['value'],
                    'dlcheck': selected_form.div.input['value'],
                }
                resp = requests.post(selected_form['action'],
                                     headers=form_headers,
                                     cookies=cookies2,
                                     data=form_data)
                archive_soup = BeautifulSoup(resp.text, 'lxml')
                p = archive_soup.find_all(id='continue')
                if not p:
                    log.error('download_archive, archive p not found')
                    return False
                href = p[0].a['href']
                time.sleep(3)
                resp = requests.get(href, headers=headers, cookies=cookies2)
                archive_real_soup = BeautifulSoup(resp.text, 'lxml')
                p = archive_real_soup.find_all('p')
                if not p:
                    log.error('download_archive, archive real p not found')
                    return False
                zip_url = replace_url_path(href, p[0].a['href'])
                title = archive_real_soup.find_all('strong')[0].text
                log.info('get archive:{} zip file url:{}'.format(
                    title, zip_url))
                original_tag = 'no_tag' if original_tag == '' else original_tag
                if env_config['ARCHIVE_DOWNLOAD_BY_ARIA'] == 'true':
                    log.info(
                        'send aria2 to download archive:{} zip file url:{}'.
                        format(title, zip_url))
                    path = env_config['ARIA_DOWN_DIR']
                    tag_path = os.path.join(path, original_tag)
                    return send_aria_download_task(title, zip_url, tag_path)
                else:
                    log.info(
                        'direct download archive:{} zip file url:{}'.format(
                            title, zip_url))
                    path = env_config['DOWN_PATH']
                    tag_path = os.path.join(path, original_tag)
                    if not os.path.exists(tag_path):
                        os.makedirs(tag_path)
                    filename = '{}.zip'.format(title)
                    filename = os.path.join(tag_path, filename)
                    return download_file(filename, zip_url, cookies2)

                return True
    return False


def find_torrent(soup, cookies2, original_tag):
    global total_download
    g2s = soup.find_all(class_='g2')
    for g2 in g2s:
        onclick = g2.a['onclick']
        if onclick and onclick.startswith(
                'return popUp(\'https://exhentai.org/gallerytorrents.php'):
            log.info('find_torrent, onclick:%s', onclick)
            p = re.compile(".+?\'(.+?)\'")
            ret = p.findall(onclick)
            if len(ret) > 0 and ret[0].startswith(
                    'https://exhentai.org/gallerytorrents.php'):
                log.info('find_torrent, get torrent address: %s', ret[0])

                response = requests.get(
                    ret[0],
                    headers=headers,
                    cookies=cookies2,
                )
                content = response.text
                soup = BeautifulSoup(content, 'lxml')
                all_a = soup.find_all('a')
                href = ''
                find_a = None
                for a in all_a:
                    if a['href'].endswith('.torrent'):
                        find_a = a
                        break
                if find_a:
                    log.info('find_torrent, get torrent address: %s',
                             find_a['onclick'])
                else:
                    log.info('find_torrent, can not get torrent address')
                    return False

                location = p.findall(find_a['onclick'])
                if len(location) != 1:
                    log.error(
                        'find_torrent, get invalid onclick torrent address: {}'
                        .format(location))
                    return False
                response = requests.get(
                    location[0],
                    headers=headers,
                    cookies=cookies2,
                )

                torrent_file = os.path.join(
                    env_config['DOWN_PATH'], '{}.torrent'.format(
                        os.path.basename(ret[0].split('/')[-1])))
                with open(torrent_file, 'wb') as f:
                    f.write(response.content)

                ret = False
                if env_config['ENABLE_QBT_TORRENT'] == 'true':
                    #ret = send_qbt_task(torrent_file=response.content)
                    ret = qbt_upload_torrent_file(
                        env_config['QBT_HOST'], env_config['QBT_USERNAME'],
                        env_config['QBT_PWD'], torrent_file,
                        env_config['QBT_CATEGORY'],
                        env_config['QBT_REMOVE_TORRENT_FILE'] == 'true',
                        original_tag)
                if env_config['ENABLE_ARIA_TORRENT'] == 'true':
                    ret = send_aria_torrent_task(response.content)
                log.info('#{} send torrent task: {}'.format(
                    total_download, ret))
                return ret

    return False


async def saveFile(image_url, path, cookiep, bar_info):
    # check local file
    local_file_size = 0
    try:
        local_file_size = os.path.getsize(path)
        log.debug('{} size={}'.format(path, local_file_size))
        if local_file_size > 20 * 1024:  # more than 20k,skip download for debug to accellerate
            log.debug('{} skipped'.format(path))
            image_url['result'] = True
            return image_url
    except:
        pass

    retry = 0
    #MAX_RETRY = env_config['MAX_RETRY']
    while retry < MAX_RETRY:
        try:
            timeout = float(env_config['CLIENT_TIMEOUT'])
            async with httpx.AsyncClient(timeout=timeout) as client:
                # response = await client.get(url,
                #                     headers=headers,
                #                     cookies=cookiep,
                #                     stream=True,
                #                     proxies=proxies)
                async with client.stream('GET',
                                         image_url['url'],
                                         headers=headers,
                                         cookies=cookiep) as response:

                    if response.status_code != 200:
                        log.error('{}, {}: status_code={}'.format(
                            image_url['url'], path, response.status_code))
                        continue
                    log.debug('remote size: {}'.format(
                        response.headers['Content-Length']))
                    remote_size = int(response.headers['Content-Length'])
                    if remote_size == local_file_size:
                        log.debug(
                            '{} local and remote has same size, skip write file'
                            .format(path))
                        image_url['result'] = True
                        return image_url
                    # TODO continue download
                    async with aiofiles.open(path, 'wb') as f:
                        #for chunk in response.iter_content(chunk_size=1024):
                        async for chunk in response.aiter_bytes(
                                chunk_size=1024):
                            await f.write(chunk)
                            await f.flush()
                    break
        except Exception as ex:
            log.error('无法下载 {}: retry: {}, {}.jpg, ex: {}'.format(
                image_url, retry, path, type(ex)))
            retry += 1
    if retry >= MAX_RETRY:
        log.error('{} download failed, retry={}'.format(path, retry))
        image_url['result'] = False
        return image_url

    image_url['result'] = True
    bar_info[1] += 1
    bar_info[0].update(bar_info[1])
    log.debug('done')
    return image_url


def get_view_images_url_list(exclude: set, url, time1, spath, cookiep,
                             bar_info):
    image_urls = []
    retry = 0
    while True:
        try:
            if cookiep != NULL:
                site = requests.get(url,
                                    headers=headers,
                                    cookies=cookiep,
                                    proxies=proxies)
            else:
                site = requests.get(url, headers=headers, proxies=proxies)
            break
        except Exception as ex:
            log.error('get_view_images_url_list 无法获取 {}: {}, 重试: {}'.format(
                url, type(ex), retry))
            retry += 1
            if retry >= 5:
                return None, None
            time.sleep(1)
    content = site.text
    soup = BeautifulSoup(content, 'lxml')
    divs = soup.find_all(class_='gdtl')
    title = soup.h1.get_text()
    rr = r"[\/\\\:\*\?\"\<\>\|]"
    new_title2 = re.sub(rr, "-", title)
    divs.sort(key=lambda x: x.img['alt'])
    for div in divs:
        picUrl = div.a.get('href')
        alt = '{}.jpg'.format(div.img['alt'])
        log.debug('下载中 {}: {}.jpg'.format(new_title2, alt))
        try:
            save_filename = os.path.join(spath, new_title2, alt)
            if alt in exclude:
                log.debug('{} skipped'.format(save_filename))
                continue
            #await saveFile(getPicUrl(picUrl, cookiep), save_filename, cookiep)
            image_url = getPicUrl(picUrl, cookiep)
            if image_url:
                image_urls.append({
                    'url': image_url,
                    'filename': save_filename,
                    'alt': alt
                })
        except Exception as ex:
            log.error('无法下载 {}: {}.jpg, ex: {}'.format(new_title2, alt,
                                                       type(ex)))
            continue

    return new_title2, image_urls


async def getWebsite(url, time1, spath, cookiep, bar_info) -> bool:

    exclude = set()
    retry = 0
    # MAX_RETRY = env_config['MAX_RETRY']
    failed_count = 0
    image_urls = []
    while True:
        if retry >= MAX_RETRY:
            return False
        tasks = []
        new_title2, image_urls = get_view_images_url_list(
            exclude, url, time1, spath, cookiep, bar_info)
        if not new_title2:
            retry += 1
        for image in image_urls:

            log.debug('下载中 {}: {}.jpg'.format(new_title2, image['alt']))
            try:
                save_filename = os.path.join(spath, new_title2, image['alt'])
                tasks.append(
                    asyncio.ensure_future(
                        saveFile(image, save_filename, cookiep, bar_info)))
            except Exception as ex:
                log.error('无法下载 {}: {}.jpg, ex: {}'.format(
                    new_title2, image['alt'], type(ex)))
                return False
            # else:
            #     log.debug('成功')
            #     bar_info[1] += 1
            #     bar_info[0].update(bar_info[1])

        image_urls = await asyncio.gather(*tasks)
        for image_url in image_urls:
            if not image_url['result']:
                failed_count += 1
            else:
                exclude.add(image_url['alt'])

        if failed_count > 0:
            retry += 1
            log.debug('{} failed:{}, retry={}'.format(new_title2, failed_count,
                                                      retry))
        else:
            break

    # if failed_count > 0:
    #     log.error('{} failed {}/{}'.format(new_title2, failed_count,
    #                                        len(image_url)))

    #     allowed_failed_percent = float(env_config['ALLOWED_FAILED_PERCENT'])
    #     failed_percent = failed_count * 100 / len(image_url)
    #     if failed_percent < allowed_failed_percent:
    #         log.info('{} failed {}%, make it success'.format(
    #             new_title2, failed_percent))
    #         return False

    #     return False

    if failed_count == 0:
        log.debug('成功 下载: {}'.format(bar_info[1]))
        endTime1 = time.time()
        log.debug("耗时：", end=' ')
        log.debug(endTime1 - time1)
        return True
    else:
        log.error('{} failed {}/{}'.format(new_title2, failed_count,
                                           len(image_urls)))

        allowed_failed_percent = float(env_config['ALLOWED_FAILED_PERCENT'])
        failed_percent = failed_count * 100 / len(image_url)
        if failed_percent < allowed_failed_percent:
            log.info('{} failed {}%, make it success'.format(
                new_title2, failed_percent))
            return True
        return False


def getPicUrl(image_url, cookiep):
    if (cookiep != NULL):
        site_2 = requests.get(image_url,
                              headers=headers,
                              cookies=cookiep,
                              proxies=proxies)
    else:
        site_2 = requests.get(image_url, headers=headers, proxies=proxies)
    content_2 = site_2.text
    soup_2 = BeautifulSoup(content_2, 'lxml')
    imgs = soup_2.find_all(id="img")

    # for img in imgs:
    #     picSrc = img['src']
    #     return picSrc
    return imgs[0]['src']


def menu_single_download(e_or_ex, cookies2):
    url = input('输入 url\n')
    # print("选择保存位置文件夹")
    # root = tk.Tk()
    # root.withdraw()
    # spath = filedialog.askdirectory() + "/"
    spath = env_config['DOWN_PATH'] + "/"
    log.info('保存路径:', spath)
    startTime1 = time.time()
    if url.find('https://e-hentai.org/g/') != -1 or url.find(
            'https://exhentai.org/g/') != -1:
        try:
            if (e_or_ex == "2"):
                site = requests.get(url,
                                    headers=headers,
                                    cookies=cookies2,
                                    proxies=proxies)
            else:
                site = requests.get(url, headers=headers, proxies=proxies)
            content = site.text
            soup = BeautifulSoup(content, 'lxml')
            divs = soup.find_all(class_='gdtl')
            title = str(soup.h1.get_text())
            page = 0
            for div in divs:
                page = page + 1
        except Exception as ex:
            log.error('错误,输入或网络问题 ' + str(ex))
            menu()
        else:
            log.info('本子名 ' + title + ',共 ' + str(page) + ' 页,开始爬取')
            rr = r"[\/\\\:\*\?\"\<\>\|]"
            new_title = re.sub(rr, "-", title)
            folder_path = os.path.join(spath, new_title)
            zip_filename = get_zip_filename_by_dir(folder_path)
            if os.path.exists(zip_filename):
                log.info('{} 已存在'.format(zip_filename))
                return
            if os.path.exists(folder_path):
                getWebsite(url, startTime1, spath, cookies2)
            else:
                os.mkdir(folder_path)
                getWebsite(url, startTime1, spath, cookies2)
    else:
        log.warning('非e站 url,重新输入\n')
        menu()


def menu_tag_urls(cookies2, f_tag, f_tag_num, star_rate, original_tag):
    page_line_count = 25
    urls = []
    base_url = 'https://exhentai.org'
    if cookies2 == NULL:
        base_url = 'https://e-hentai.org'
    url = '{}/?f_cats=1019&f_search={}&advsearch=1&f_stags=on&f_sr=on&f_srdd={}&page='.format(
        base_url, f_tag, star_rate)
    log.info('开始搜索:{}, 页数:{}, 标签:{}, original tag:{}, 星级:{}'.format(
        url, f_tag_num, f_tag, original_tag, star_rate))
    try:
        int_pages = f_tag_num // page_line_count
        line_mod = f_tag_num % page_line_count
        for int_page in range(0, int_pages + 1):
            if cookies2 != NULL:
                site = requests.get(url + str(int_page),
                                    headers=headers,
                                    cookies=cookies2,
                                    proxies=proxies)
            else:
                site = requests.get(url + str(int_page),
                                    headers=headers,
                                    proxies=proxies)
            content = site.text
            if content.startswith(
                    'Your IP address has been temporarily banned'):
                ban_time = get_ban_time_from_text(content)
                log.warning('get banned, wait for: {}, at time: {}'.format(
                    ban_time,
                    (datetime.now() + ban_time).strftime('%Y-%m-%d %H:%M:%S')))
                time.sleep(ban_time.total_seconds())
                return []
            soup = BeautifulSoup(content, 'lxml')
            tds = soup.find_all(class_='glname')
            log.info('当前页面:{}, tds count:{}'.format(url, len(tds)))
            if len(tds) < 1:
                log.info('当前页面:{}, tds count:{}'.format(url, len(tds)))
                return []
            for index, a in enumerate(tds):
                href = a.parent['href']
                log.debug(str(int_page * 25 + index + 1) + ':' + href)
                urls.append(href)

                if (25 > f_tag_num - 1 ==
                        index) or (f_tag_num > 25 and int_page == int_pages
                                   and index == line_mod - 1):
                    break
            time.sleep(float(env_config['SLEEP_TIME_PER_BOOK']))
    except Exception as ex:
        log.error('menu_tag_urls, 错误,输入或网络问题, ex:%s', type(ex))

    return urls


def menu_tag_download(url, cookies2, spath, startTime1, original_tag):
    global total_download
    try:
        log.info('menu_tag_download, tag:{}, url:{}'.format(original_tag, url))
        if cookies2 != NULL:
            site = requests.get(url,
                                headers=headers,
                                cookies=cookies2,
                                proxies=proxies)
        else:
            site = requests.get(url, headers=headers, proxies=proxies)
        content = site.text
        soup = BeautifulSoup(content, 'lxml')

        downloaded = False
        if env_config['ENABLE_DOWNLOAD_ARCHIVE'] == 'true':
            downloaded = download_archive(soup, cookies2, spath, original_tag)

        if not downloaded:
            if find_torrent(soup, cookies2, original_tag):
                redis_conn.srem(DOWNLOADING_URL_REDIS_KEY, url)
                redis_conn.sadd(TORRENT_URL_REDIS_KEY, url)
                total_download += 1
                return

            elif env_config['ENABLE_IMAGE_DOWNLOAD'] != 'true':
                log.info('ENABLE_IMAGE_DOWNLOAD is false, skip image download')
                redis_conn.srem(DOWNLOADING_URL_REDIS_KEY, url)
                redis_conn.sadd(SKIPPED_URL_REDIS_KEY, url)

        table = soup.find_all(class_='ptt')
        tds = table[0].find_all('td')
        view_count = 0
        for td in tds:
            if 'onclick' in td.attrs:
                if td['onclick'] == 'document.location=this.firstChild.href':
                    view_count += 1
        if view_count == 0: view_count = 1
        divs = soup.find_all(class_='gdtl')
        title = str(soup.h1.get_text())
        # page = 0
        # for div in divs:
        #     page = page + 1
    except Exception as ex:
        log.error('menu_tag_download: 错误,输入或网络问题: %s', ex)
        return
    else:
        s = '#{} 本子名:{},views:{},开始爬取'.format(total_download, title,
                                              view_count)
        log.info(s)
        rr = r"[\/\\\:\*\?\"\<\>\|]"
        new_title = re.sub(rr, "-", title)
        folder_path = os.path.join(spath, new_title)
        zip_filename = get_zip_filename_by_dir(folder_path)
        if os.path.exists(zip_filename):
            log.info('{} ZIP已存在'.format(zip_filename))
            return
        if not os.path.exists(folder_path):
            os.mkdir(folder_path)

        index = 0
        success = True
        with progressbar.ProgressBar(max_value=view_count * 20) as bar:
            bar_info = [bar, index]
            for view in range(0, view_count):
                time.sleep(float(env_config['SLEEP_TIME_PER_VIEW_PAGE']))
                log.debug('当前view:{}'.format(view + 1))
                if view == 0:
                    view_url = url
                else:
                    view_url = '{}?p={}'.format(url, view + 1)
                ret = asyncio.run(
                    getWebsite(view_url, startTime1, spath, cookies2,
                               bar_info))
                # TODO failed asyncio job handle
                if not ret:
                    log.error('{} 当前view:{}: failed asyncio job handle'.format(
                        new_title, view + 1))
                    success = False
                    continue
        if not success:
            redis_conn.srem(DOWNLOADING_URL_REDIS_KEY, url)
            redis_conn.sadd(FAILED_URL_REDIS_KEY, url)
            return

        log.info('#{} 生成zip 文件: {}'.format(total_download, zip_filename))
        make_zip(folder_path, True)
        log.info('#{} 生成zip 文件: {} 完成'.format(total_download, zip_filename))

        redis_conn.sadd(DOWNLOADED_URL_REDIS_KEY, url)
        redis_conn.srem(DOWNLOADING_URL_REDIS_KEY, url)
        total_download += 1


def tag_multiprocessing(m_urls: list, cookies2, original_tag):
    # m_urls = ['https://e-hentai.org/g/2118247/5445976a9e/']
    if 'https://e-hentai.org/g/2118247/5445976a9e/' in m_urls:
        m_urls.remove('https://e-hentai.org/g/2118247/5445976a9e/')

    for url in m_urls:
        if redis_conn.smismember(DOWNLOADED_URL_REDIS_KEY, url)[0]:
            m_urls.remove(url)
            log.info('{} 已经下载过了'.format(url))
            continue

    # print("选择保存位置文件夹")
    # root = tk.Tk()
    # root.withdraw()
    # spath = filedialog.askdirectory() + "/"
    spath = env_config['DOWN_PATH'] + "/"
    startTime1 = time.time()
    max_process_num = int(env_config['PROCESS_NUM'])
    for url in m_urls:
        menu_tag_download(url, cookies2, spath, startTime1, original_tag)
        time.sleep(float(env_config['SLEEP_TIME_PER_BOOK']))
    # pool = multiprocessing.Pool(processes=max_process_num)
    # for url in m_urls:
    #     log.info(url)
    #     pool.apply_async(menu_tag_download, (url, cookies2, spath, startTime1))
    # pool.close()
    # pool.join()


def menu():
    cookies2 = NULL
    m_urls = []
    #e_or_ex = input('ehentai输入1----exhentai输入2----按tag爬取输入3\n')
    e_or_ex = env_config['SEARCH_TYPE']
    if e_or_ex == "1":
        menu_single_download(e_or_ex, cookies2)
    if e_or_ex == "2":
        cookies_input = input(
            '输入exhentai的cookies(在exhentai的页面下，在控制台中输入document.cookie所得到的内容)\n')
        cookies2 = dict(map(lambda x: x.split('='), cookies_input.split(";")))
        menu_single_download(e_or_ex, cookies2)
    if e_or_ex == "3":
        # tag_e_or_ex = input('ehentai输入1----exhentai输入2\n')
        tag_e_or_ex = env_config['EH_SOURCE']
        if tag_e_or_ex == '2':
            # cookies_input = input(
            #     '输入exhentai的cookies(在exhentai的页面下，在控制台中输入document.cookie所得到的内容)\n'
            # )
            cookies_input = env_config['EH_COOKIE']
            cookies2 = dict(
                map(lambda x: x.split('='), cookies_input.split(";")))

        # resuming download
        download_redis_set(cookies2, DOWNLOADING_URL_REDIS_KEY)

        # continue queued
        download_redis_set(cookies2, QUEUED_URL_REDIS_KEY)

        # retry failed
        download_redis_set(cookies2, FAILED_URL_REDIS_KEY)

        f_tags = env_config['EH_TAGS']
        f_language = env_config['EH_LANGUAGE']
        star_rate = env_config['EH_STAR']
        tags = f_tags.split(';')
        for tag_index, tag in enumerate(tags):
            if f_language:
                tag = '{} + l:{}$'.format(tag, f_language)
            f_tag = urllib.parse.quote(tag)
            # f_tag_num = input('输入下载数量\n')
            f_tag_num = env_config['EH_DOWN_NUM']
            f_tag_num = int(f_tag_num)
            log.info('开始搜索标签:{}, 数量:{}, 第{}/{}个'.format(
                tag, f_tag_num, tag_index, len(tags)))

            m_urls = menu_tag_urls(cookies2, f_tag, f_tag_num, star_rate, tag)
            for url in m_urls:
                redis_conn.sadd(QUEUED_URL_REDIS_KEY, url)

            urls = list(redis_conn.smembers(QUEUED_URL_REDIS_KEY))[:10]
            urls = [url.decode('utf-8') for url in urls]
            for url in urls:
                redis_conn.sadd(DOWNLOADING_URL_REDIS_KEY, url)
                redis_conn.srem(QUEUED_URL_REDIS_KEY, url)
            tag_multiprocessing(urls, cookies2, tag)

            if (redis_conn.scard(DOWNLOADED_URL_REDIS_KEY) == 0
                    and redis_conn.scard(QUEUED_URL_REDIS_KEY) == 0):
                # use failed queue
                urls = list(redis_conn.smembers(FAILED_URL_REDIS_KEY))[:10]
                urls = [url.decode('utf-8') for url in urls]
                for url in urls:
                    redis_conn.sadd(DOWNLOADING_URL_REDIS_KEY, url)
                    redis_conn.srem(FAILED_URL_REDIS_KEY, url)
            tag_multiprocessing(urls, cookies2, tag)


def download_redis_set(cookies2, set_key_name):
    urls = list(redis_conn.smembers(set_key_name))
    log.info('{} urls in redis set:{}'.format(len(urls), set_key_name))
    urls.sort()
    if len(urls) > 0:
        urls = [url.decode('utf-8') for url in urls[:10]]
        tag_multiprocessing(urls, cookies2, "")


if __name__ == "__main__":
    log.info('e-hentai crawler, version:{}'.format(VERSION))
    multiprocessing.freeze_support()
    menu()

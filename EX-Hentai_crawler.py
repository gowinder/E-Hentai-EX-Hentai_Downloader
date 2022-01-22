# -*- coding: utf-8 -*-
import multiprocessing
import os
import re
import time
import urllib
from json import load
from turtle import onclick

import requests
#from _overlapped import NULL
from bs4 import BeautifulSoup
from dotenv import dotenv_values
from redis import Redis

env_config = dotenv_values()

DOWNLOADED_URL_REDIS_KEY = 'downloaded_urls'
redis_conn = Redis.from_url(os.environ.get('REDIS_URL'))

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


def saveFile(url, path, cookiep):
    # check local file
    local_file_size = 0
    try:
        local_file_size = os.path.getsize(path)
        print('{} size={}'.format(path, local_file_size))
    except:
        pass

    if (cookiep != NULL):
        response = requests.get(url, headers=headers, cookies=cookiep)
    else:
        response = requests.get(url, headers=headers)
    print('remote size: {}'.format(response.headers['Content-Length']))
    if int(response.headers['Content-Length']) == local_file_size:
        print(
            '{} local and remote has same size, skip write file'.format(path))
        return
    with open(path, 'wb') as f:
        f.write(response.content)
        f.flush()
    print('done')


def getWebsite(url, time1, spath, cookiep):
    if cookiep != NULL:
        site = requests.get(url, headers=headers, cookies=cookiep)
    else:
        site = requests.get(url, headers=headers)
    content = site.text
    soup = BeautifulSoup(content, 'lxml')
    divs = soup.find_all(class_='gdtl')
    title = soup.h1.get_text()
    rr = r"[\/\\\:\*\?\"\<\>\|]"
    new_title2 = re.sub(rr, "-", title)
    i = 0
    divs.sort(key=lambda x: x.img['alt'])
    for div in divs:
        picUrl = div.a.get('href')
        alt = '{}.jpg'.format(div.img['alt'])
        print('下载中 {}: {}.jpg'.format(new_title2, alt))
        try:
            save_filename = os.path.join(spath, new_title2, alt)
            saveFile(getPicUrl(picUrl, cookiep), save_filename, cookiep)
        except Exception as ex:
            print('无法下载 {}: {}.jpg'.format(new_title2, alt))
        else:
            print('成功')
            i = i + 1
    print('成功 下载: {}'.format(i))
    endTime1 = time.time()
    print("耗时：", end=' ')
    print(endTime1 - time1)


def getPicUrl(url, cookiep):
    if (cookiep != NULL):
        site_2 = requests.get(url, headers=headers, cookies=cookiep)
    else:
        site_2 = requests.get(url, headers=headers)
    content_2 = site_2.text
    soup_2 = BeautifulSoup(content_2, 'lxml')
    imgs = soup_2.find_all(id="img")
    for img in imgs:
        picSrc = img['src']
        return picSrc


def menu_single_download(e_or_ex, cookies2):
    url = input('输入 url\n')
    # print("选择保存位置文件夹")
    # root = tk.Tk()
    # root.withdraw()
    # spath = filedialog.askdirectory() + "/"
    spath = env_config['DOWN_PATH'] + "/"
    print('保存路径:', spath)
    startTime1 = time.time()
    if url.find('https://e-hentai.org/g/') != -1 or url.find(
            'https://exhentai.org/g/') != -1:
        print('--获取信息中--')
        try:
            if (e_or_ex == "2"):
                site = requests.get(url, headers=headers, cookies=cookies2)
            else:
                site = requests.get(url, headers=headers)
            content = site.text
            soup = BeautifulSoup(content, 'lxml')
            divs = soup.find_all(class_='gdtl')
            title = str(soup.h1.get_text())
            page = 0
            for div in divs:
                page = page + 1
        except Exception as ex:
            print('错误,输入或网络问题 ' + str(ex))
            menu()
        else:
            print('本子名 ' + title + ',共 ' + str(page) + ' 页,开始爬取')
            rr = r"[\/\\\:\*\?\"\<\>\|]"
            new_title = re.sub(rr, "-", title)
            if os.path.exists(spath + new_title):
                getWebsite(url, startTime1, spath, cookies2)
            else:
                os.mkdir(spath + new_title)
                getWebsite(url, startTime1, spath, cookies2)
    else:
        print('非e站 url,重新输入\n')
        menu()


def menu_tag_urls(cookies2, f_tag, f_tag_num):
    page_line_count = 25
    urls = []
    if cookies2 != NULL:
        url = 'https://exhentai.org/?f_cats=1019&f_search=' + f_tag + '&page='
    else:
        url = 'https://e-hentai.org/?f_cats=1019&f_search=' + f_tag + '&page='

    print('爬取前' + str(f_tag_num) + '本')
    print('--获取信息中--')
    try:
        int_pages = f_tag_num // page_line_count
        line_mod = f_tag_num % page_line_count
        for int_page in range(0, int_pages + 1):
            if cookies2 != NULL:
                site = requests.get(url + str(int_page),
                                    headers=headers,
                                    cookies=cookies2)
            else:
                site = requests.get(url + str(int_page), headers=headers)
            content = site.text
            soup = BeautifulSoup(content, 'lxml')
            tds = soup.find_all(class_='glname')
            print('当前页面:' + url + str(int_page))
            for index, a in enumerate(tds):
                href = a.parent['href']
                print(str(int_page * 25 + index + 1) + ':' + href)
                urls.append(href)

                if (25 > f_tag_num - 1 ==
                        index) or (f_tag_num > 25 and int_page == int_pages
                                   and index == line_mod - 1):
                    break
    except Exception as ex:
        print('错误,输入或网络问题')
        raise ex
        menu()
    else:
        return urls


def menu_tag_download(url, cookies2, spath, startTime1):
    try:
        print('menu_tag_download')
        if cookies2 != NULL:
            site = requests.get(url, headers=headers, cookies=cookies2)
        else:
            site = requests.get(url, headers=headers)
        content = site.text
        soup = BeautifulSoup(content, 'lxml')
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
        print('错误,输入或网络问题: ' + str(ex))
        menu()
    else:
        s = '本子名:{},views:{},开始爬取'.format(title, view_count)
        print(s)
        rr = r"[\/\\\:\*\?\"\<\>\|]"
        new_title = re.sub(rr, "-", title)
        if not os.path.exists(spath + new_title):
            os.mkdir(spath + new_title)
        for view in range(0, view_count):
            print('当前view:{}'.format(view + 1))
            view_url = '{}?p={}'.format(url, view + 1)
            getWebsite(view_url, startTime1, spath, cookies2)

        redis_conn.sadd(DOWNLOADED_URL_REDIS_KEY, url)


def tag_multiprocessing(m_urls: list, cookies2):
    # m_urls = ['https://e-hentai.org/g/2118247/5445976a9e/']
    if 'https://e-hentai.org/g/2118247/5445976a9e/' in m_urls:
        m_urls.remove('https://e-hentai.org/g/2118247/5445976a9e/')

    for url in m_urls:
        if redis_conn.smismember(DOWNLOADED_URL_REDIS_KEY, url)[0]:
            m_urls.remove(url)
            print('{} 已经下载过了'.format(url))
            continue

    # print("选择保存位置文件夹")
    # root = tk.Tk()
    # root.withdraw()
    # spath = filedialog.askdirectory() + "/"
    spath = env_config['DOWN_PATH'] + "/"
    print('保存路径:', spath)
    startTime1 = time.time()
    print('--获取信息中--')
    pool = multiprocessing.Pool(processes=10)
    for url in m_urls:
        print(url)
        pool.apply_async(menu_tag_download, (url, cookies2, spath, startTime1))
    pool.close()
    pool.join()


def menu():
    cookies2 = NULL
    m_urls = []
    print("E-Hentai&EX-Hentai下载器V1.2")
    print('可爬取e-hentai和exhentai的表里站下的内容')
    print('Win10下使用可能会有卡住窗口缓冲区的问题，若遇到某张图片久久没有下载成功的情况，按任意键即可')
    print('*****注意*****需要爬取ehentai还是exhentai?')
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
        # f_tag = input(
        #     '输入tag--xxxx:xxx形式,多个tag示例--language:xx f:xxx--多个tag间用空格隔开\n')
        f_tag = env_config['EH_TAG']
        f_tag = urllib.parse.quote(f_tag)
        print(f_tag)
        # f_tag_num = input('输入下载数量\n')
        f_tag_num = env_config['EH_DOWN_NUM']
        f_tag_num = int(f_tag_num)
        m_urls = menu_tag_urls(cookies2, f_tag, f_tag_num)

        tag_multiprocessing(m_urls, cookies2)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    menu()

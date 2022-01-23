from datetime import datetime
import sys
import datetime
from crawler import menu_tag_download
from bs4 import BeautifulSoup
from dotenv import dotenv_values

env_config = dotenv_values()

cookie = env_config.get('EH_COOKIE')

cookies2 = dict(map(lambda x: x.split('='), cookie.split(";")))

if __name__ == '__main__':
    url = env_config['EH_TEST_URL']
    menu_tag_download(url, cookies2, '', datetime.datetime.now())
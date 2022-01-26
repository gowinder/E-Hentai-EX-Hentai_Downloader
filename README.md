# readme

## reference

base on `https://github.com/TennoClash/E-Hentai-EX-Hentai_Downloader`

## add feature

- major change on tag search
- muliple tag search
- get book torrent file
  - support aria2, qbt api
- use redis to store downloaded url

## how to use

### .env

- `SEARCH_TYPE`: "3" for tag search result crawler
- `DOWN_PATH`: download file store root directory
- `EH_COOKIE`: cookie for e-hentai site logined, eg: `event=...;ipb_member_id=...;ipb_pass_hash=...;sk=...;`
- `EH_TAG`: useless now
- `EH_TAGS`: tags for search, use `;` to combine, eg: `"x:xx$;x:xx$"`, note`: each tag end with `$`
- `EH_STAR`: search star rate, eg: `4` for more than 4
- `EH_SOURCE`: site type`: 1=eh 2=exh
- `EH_DOWN_NUM`: crawler result number, maybe 50?
- `REDIS_URL`: redis for cache, eg: `redis://localhost:6379/0`
- `PROXY_POOL_ADDR`: useless now
- `PROCESS_NUM`: useless now
- `CLIENT_TIMEOUT`: timeout for request.get() for image
- `ALLOWED_FAILED_PERCENT`: allow failed percent, when ENABLE_IMAGE_DOWNLOAD=true, will download image, `eh` use `p2p` to serve the image download, so it may be failed, when failed percent below ALLOWED_FAILED_PERCENT, let is be succeed, make the zip, avoid continue downloading
- `MAX_RETRY`: for all failed retry count
- `ENABLE_IMAGE_DOWNLOAD`: enable direct download image, these will cause anti-crawler, suggest false
- `SLEEP_TIME_PER_BOOK`: sleep time for every book download even if failed or skipped
- `SLEEP_TIME_PER_VIEW_PAGE`: sleep time for image download every page view (20 image one view default)
- `ENABLE_QBT_TORRENT`: enable qbt torrent task add
- `QBT_HOST`: eg: `http://localhost:7081`
- `QBT_PORT`: useless
- `QBT_USERNAME`: qbt webui username
- `QBT_PWD`: qbt webui password
- `QBT_CATEGORY`: qbt category
- `QBT_REMOVE_TORRENT_FILE`: remove torrent file after qbt torrent add succeed
- `EH_TEST_URL`: for test using
- `ENABLE_ARIA_TORRENT`: enable aria2 rpc task add
- `ARIA_RPC_ADDRESS`: eg:`http://localhost:6800/jsonrpc`
- `ARIA_RPC_SECRET`: aria2 rpc secret
- `ARIA_DOWN_DIR`: aria2 download path

### python3

currently we use develop branch

```shell
pip3 install -r requirements.txt
cp .env.sample
# edit .env file
# vim .env
python3 crawler.py
```

### docker compose

```shell
cp .env.sample .env.docker
# edit .env.docker file
docker-compose build
docker-compose up -d
```

## TODO

- [ ] add book type to configure
- [ ] add proxy pool
- [ ] moniter rss and downlaod
- [ ] add no torrent url to new redis set when ENABLE_IMAGE_DOWNLOAD=false

import logging

import coloredlogs

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
log.addHandler(console_handler)
coloredlogs.install(level='INFO')

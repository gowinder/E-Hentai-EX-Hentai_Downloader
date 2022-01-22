import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
log.addHandler(console_handler)

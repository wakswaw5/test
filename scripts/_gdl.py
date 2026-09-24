"""Pembungkus kecil untuk memakai extractor gallery-dl sebagai library.

gallery-dl memberi extractor sebuah logger khusus (dengan metode .traceback()) hanya
saat dijalankan lewat CLI/Job. Kalau extractor dipakai langsung, self.log adalah
logging.Logger biasa dan extractor akan crash dengan
"'Logger' object has no attribute 'traceback'" begitu ia mencoba mencatat error
non-fatal. Helper ini menambal itu dan menyalakan logging supaya peringatan terlihat.
"""

import logging
import sys


class _Log:
    """Logger biasa + metode traceback() seperti gallery_dl.output.LoggerAdapter."""

    def __init__(self, logger):
        self._logger = logger

    def traceback(self, exc):
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("", exc_info=exc)

    def __getattr__(self, name):
        return getattr(self._logger, name)


def make_extractor(url, browser=None, options=()):
    """Kembalikan extractor gallery-dl siap pakai (sudah initialize()).

    browser : nama browser untuk cookie (mis. "firefox"), None = tanpa cookie
    options : iterable of (section_tuple, key, value) untuk config.set
    """
    from gallery_dl import config, extractor

    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.WARNING, stream=sys.stderr,
                            format="[%(name)s][%(levelname)s] %(message)s")
    if browser:
        config.set(("extractor",), "cookies", (browser,))
    for section, key, value in options:
        config.set(section, key, value)

    ex = extractor.find(url)
    if ex is None:
        raise ValueError(f"gallery-dl tidak mengenali URL: {url}")
    ex.log = _Log(ex.log)
    ex.initialize()
    return ex

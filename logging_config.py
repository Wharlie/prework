import logging


def setup_logging(level: int = logging.INFO) -> None:
    """配置 logging 模块"""
    if level <= logging.DEBUG and level != logging.NOTSET:
        fmt = (
            "%(asctime)s"
            "#%(processName)s(%(process)d)"
            "#%(threadName)s(%(thread)d)"
            "#%(pathname)s#%(funcName)s#%(lineno)d"
            "#%(name)s-%(levelname)s: %(message)s"
        )
    else:
        fmt = (
            "%(asctime)s"
            "#%(processName)s(%(process)d)"
            "#%(name)s-%(levelname)s: %(message)s"
        )

    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
    )


if __name__ == "__main__":
    setup_logging(logging.DEBUG)
    logging.debug("debug message")
    logging.info("info message")
    logging.warning("warning message")
    logging.error("error message")
    logging.critical("critical message")

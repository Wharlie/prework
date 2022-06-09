from abc import ABC, abstractmethod
from configparser import ConfigParser as IniConfigParser
from dataclasses import dataclass, field
from json import loads
from logging import Logger, getLogger
from os import close, dup2, fdopen, pipe
from pathlib import Path
from re import sub
from threading import Timer
from typing import IO, Any, Callable, ClassVar, Optional, Type, cast

from pydantic import BaseModel


@dataclass
class ServerBase(ABC):
    """服务端基类"""

    config_file_name: ClassVar[str]

    dir_path: Path
    config: BaseModel = field(default_factory=BaseModel, init=False)
    _logger: Optional[Logger] = field(default=None, init=False)

    @property
    def name(self) -> str:
        return self.dir_path.name

    @property
    def config_path(self) -> Path:
        return self.dir_path / self.config_file_name

    @property
    def logger(self) -> Logger:
        if not self._logger:
            self._logger = getLogger(self.name)
        return self._logger

    @abstractmethod
    def is_running(self) -> bool:
        """是否在运行中"""
        ...

    @abstractmethod
    def start(self) -> None:
        """启动"""
        ...

    @abstractmethod
    def stop(self) -> None:
        """停止"""
        ...

    @staticmethod
    def _timeout_call(
        func: Callable,
        timeout: float,
        error_message: str = "Timeout",
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
    ) -> Any:
        """调用对应函数，超时则抛出异常"""
        args = args or ()
        kwargs = kwargs or {}

        def handle_timeout():
            raise TimeoutError(error_message)

        timer = Timer(interval=timeout, function=handle_timeout)
        timer.start()
        result = func(*args, **kwargs)
        timer.cancel()
        return result

    @staticmethod
    def _open_inheritable_pipe(target_fd: int, mode: str) -> IO:
        """打开可继承的管道"""
        rfd, wfd = pipe()
        match mode:
            case w_mode if "w" in w_mode:
                return_fd = wfd
                relay_fd = rfd
            case r_mode if "r" in r_mode:
                return_fd = rfd
                relay_fd = wfd
            case _:
                raise ValueError(f"未知的模式 {mode}")
        dup2(relay_fd, target_fd, inheritable=True)
        close(relay_fd)
        return fdopen(fd=return_fd, mode=mode)

    @staticmethod
    def _convert_table_to_dict(table_str: str) -> dict:
        """将表示 lua 中 table 的字符串转为 Python 中的 dict"""
        s = table_str.replace("=", ":").replace('["', '"').replace('"]', '"')
        s = sub(r"(?P<key>[\w.]+)(?=\s*?:)", r'"\g<key>"', s)  # 键加双引号
        s = sub(r",(?=\s*?[}|\]])", r"", s)  # 去列表尾逗号
        json_obj = loads(s if s else "{}")
        return dict(json_obj)

    @classmethod
    def _extract_data(cls, path: str) -> dict:
        """提取存档文件中易识别的 lua 数据"""
        with open(path, "r") as f:
            raw_str = f.read()
        table_str = raw_str[raw_str.find("{") : raw_str.find("\x00")]
        return cls._convert_table_to_dict(table_str)

    @staticmethod
    def _load_ini(ini_path: Path) -> dict:
        """加载 ini 配置文件"""
        # 配置文件可能为手工编辑，会出现留空的情况
        # 允许留空
        ini_parser = IniConfigParser(allow_no_value=True)
        with ini_path.open(mode="rt", encoding="utf-8") as ini_file:
            ini_parser.read_file(ini_file)

        # ini_parser 支持常见的 dict 操作
        # 具体地说是实现了 collections.abc.MutableMapping 可变映射接口
        # 但它会额外加载一个 "DEFAULT" section
        # 这里转化成标准的 dict
        d = dict()
        for section_name in ini_parser.sections():
            for key, value in ini_parser[section_name].items():
                # 滤除空值
                if value is not None:
                    d[section_name] = {key: value}
        return d

    @staticmethod
    def _save_ini(ini_dict: dict, ini_path: Path) -> None:
        """保存 ini 配置文件"""
        ini_parser = IniConfigParser()
        ini_parser.read_dict(ini_dict)
        with ini_path.open(mode="wt", encoding="utf-8") as ini_file:
            ini_parser.write(ini_file)

    def load_config(self, config_path: Optional[Path] = None) -> None:
        """加载配置"""
        config_path = config_path or self.config_path
        config_mode_class = type(self.config)

        if config_path.exists():
            self.logger.info(f"加载配置文件 {config_path}")
            config_dict = self._load_ini(config_path)
            config = config_mode_class.parse_obj(config_dict)
        else:
            self.logger.warning(f"配置文件 {config_path} 不存在，生成并加载默认配置文件")
            config = config_mode_class()
            self.save_config(config, config_path)

        self.config = config

    def save_config(
        self, config: Optional[BaseModel] = None, config_path: Optional[Path] = None
    ) -> None:
        """保存 ini 配置文件"""
        config = config or self.config
        config_path = config_path or self.config_path

        self.logger.info(f"保存配置文件 {config_path}")
        self._save_ini(config.dict(), config_path)

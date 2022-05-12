from abc import ABC, abstractmethod
from configparser import ConfigParser as IniConfigParser
from dataclasses import dataclass, field
from enum import Enum
from json import loads
from logging import Logger, getLogger
from pathlib import Path
from re import sub
from typing import ClassVar, Optional

from pydantic import BaseModel


class Arch(Enum):
    """架构枚举"""

    x86 = 32
    i386 = 32
    amd64 = 64
    x86_64 = 64
    x64 = 64

class Timer:
    """TODO:定时器"""
    # from threading import Timer
    pass

@dataclass
class ServerBase(ABC):
    """服务端基类"""

    config_file_name: ClassVar[str]

    dir_path: Path
    config: BaseModel
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
    def start(self) -> None:
        """启动"""
        ...

    @abstractmethod
    def stop(self) -> None:
        """停止"""
        ...

    @abstractmethod
    def restart(self) -> None:
        """重启"""
        ...

    @staticmethod
    def _convert_table_to_dict(table_str: str) -> dict:
        """将表示 lua 中 table 的字符串转为 Python 中的 dict"""
        s = table_str.replace("=", ":").replace('["', '"').replace('"]', '"')
        s = sub(r"(?P<key>[\w.]+)(?=\s*?:)", r'"\g<key>"', s)  # 键加双引号
        s = sub(r",(?=\s*?[}|\]])", r"", s)  # 去列表尾逗号
        json_obj = loads(s if s else "{}")
        return dict(json_obj)

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
        # 但它会强制加载一个 "DEFAULT" section
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

    def load_ini(self, ini_path: Optional[Path] = None) -> None:
        """加载 ini 配置文件"""
        ini_path = ini_path or self.config_path
        self.logger.info(f"加载配置文件 {ini_path}")
        config_dict = self._load_ini(ini_path)
        self.config.parse_obj(config_dict)

    def save_ini(self, ini_path: Optional[Path] = None) -> None:
        """保存 ini 配置文件"""
        ini_path = ini_path or self.config_path
        self.logger.info(f"保存配置文件 {ini_path}")
        config_dict = self.config.dict()
        self._save_ini(config_dict, ini_path)

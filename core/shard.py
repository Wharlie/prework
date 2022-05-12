from dataclasses import dataclass
from ipaddress import IPv4Address
from os import getpid
from pathlib import Path
from random import randrange
from subprocess import PIPE, Popen
from typing import ClassVar, Iterable, Optional

from pydantic import BaseModel, Field

from ._server_base import ServerBase
from .cluster import Cluster


class ServerShardModel(BaseModel):
    """服务端分片配置模型"""

    is_master: bool
    name: str
    id: int = Field(default_factory=lambda: randrange(2**32))
    bind_ip: Optional[IPv4Address] = None
    master_ip: Optional[IPv4Address] = None
    master_port: Optional[int] = None
    cluster_key: Optional[str] = None


class ServerSteamModel(BaseModel):
    """服务端 Steam 配置模型"""

    authentication_port: int = 8766
    master_server_port: int = 27016


class ServerNetworkModel(BaseModel):
    """服务端网络配置模型"""

    server_port: int = 10999


class ServerAccountModel(BaseModel):
    """服务端账户配置模型"""

    encode_user_path: bool = False


class ServerIniModel(BaseModel):
    """服务端配置模型（server.ini）"""

    shard: ServerShardModel
    steam: ServerSteamModel
    network: ServerNetworkModel
    account: ServerAccountModel


@dataclass
class Shard(ServerBase):
    """分片"""

    config_file_name: ClassVar[str] = "server.ini"

    cluster: Cluster
    config: ServerIniModel
    dst_bin_path: Path

    def _extract_data(self, path: str):
        """提取存档文件中易识别的 lua 数据"""
        with open(path, "r") as f:
            raw_str = f.read()
        table_str = raw_str[raw_str.find("{") : raw_str.find("\x00")]
        return self._convert_table_to_dict(table_str)

    def _remove_server_temp(self) -> None:
        """删除服务端临时文件"""
        server_temp_path = self.dir_path / "save/server_temp/server_save"
        self.logger.debug(f"删除服务端临时文件 {server_temp_path}")
        server_temp_path.unlink(missing_ok=True)

    def _start(
        self,
        remove_server_temp: bool = True,
        skip_update_server_mods: bool = True,
        extra_args: Optional[Iterable[str]] = None,
    ) -> None:
        """底层启动方法"""
        if remove_server_temp:
            self._remove_server_temp()

        cmd_list = [str(self.dst_bin_path)]
        cmd_list += ("-cloudserver",)
        cmd_list += ("persistent_storage_root", str(self.cluster.data_root_path))
        cmd_list += ("-conf_dir", str(self.cluster.conf_dir_path))
        cmd_list += ("-cluster", self.cluster.name)
        cmd_list += ("-shard", self.name)
        cmd_list += ("-ugc_directory", str(self.cluster.ugc_path))
        cmd_list += ("-monitor_parent_process", str(getpid()))

        if skip_update_server_mods:
            self.logger.debug("跳过更新服务端 mod")
            cmd_list += ("-skip_update_server_mods",)

        if extra_args:
            self.logger.debug(f"额外参数: {extra_args}")
            cmd_list += extra_args

        shard_process = Popen(
            # TODO: 子进程调用
            cmd_list,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
            cwd=self.dst_bin_path.parent,
            text=True,
        )

    def start(self) -> None:
        """启动分片"""
        self._start()

    def stop(self, save: bool = True, timeout: int = 10) -> None:
        """停止分片"""
        pass

    def restart(self) -> None:
        """重启"""
        self.stop()
        self._start(remove_server_temp=False)

    def update_mod(self) -> None:
        """更新 mod"""
        self.logger.info("更新 mod")
        self._start(
            skip_update_server_mods=False, extra_args=("-only_update_server_mods",)
        )
        self.stop()

    def _stop(self) -> None:
        """关闭"""
        pass

    def _save(self) -> None:
        """存档"""
        pass

    def _announce(self) -> None:
        """公告"""

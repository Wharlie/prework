from dataclasses import dataclass, field
from ipaddress import IPv4Address
from os import getpid
from pathlib import Path
from random import randrange
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired
from typing import ClassVar, Iterable, Optional, TextIO, cast

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

    _fd3_file: Optional[TextIO] = field(default=None, init=False)
    _fd4_file: Optional[TextIO] = field(default=None, init=False)
    _fd5_file: Optional[TextIO] = field(default=None, init=False)
    _process: Optional[Popen] = field(default=None, init=False)

    def _remove_server_temp(self) -> None:
        """删除服务端临时文件"""
        server_temp_path = self.dir_path / "save/server_temp/server_save"
        self.logger.debug(f"删除服务端临时文件 {server_temp_path}")
        server_temp_path.unlink(missing_ok=True)

    def _open_fd_files(self) -> None:
        """打开文件描述符"""
        self.logger.debug("打开文件描述符")
        self._fd3_file = self._fd3_file or cast(
            TextIO, self._open_inheritable_pipe(3, "wt")
        )
        self._fd4_file = self._fd4_file or cast(
            TextIO, self._open_inheritable_pipe(4, "rt")
        )
        self._fd5_file = self._fd5_file or cast(
            TextIO, self._open_inheritable_pipe(5, "rt")
        )

    def _start(
        self,
        skip_update_server_mods: bool = True,
        remove_server_temp: bool = True,
        extra_args: Optional[Iterable[str]] = None,
    ) -> None:
        """底层启动方法"""

        cmd_list = [str(self.cluster.dst_bin_path)]
        cmd_list += ("-cloudserver",)
        cmd_list += ("persistent_storage_root", str(self.cluster.data_root_path))
        cmd_list += ("-conf_dir", str(self.cluster.conf_dir_path))
        cmd_list += ("-cluster", self.cluster.name)
        cmd_list += ("-shard", self.name)
        cmd_list += ("-ugc_directory", str(self.cluster.ugc_path))
        cmd_list += ("-monitor_parent_process", str(getpid()))

        if skip_update_server_mods:
            self.logger.debug("跳过服务端 mod 更新")
            cmd_list += ("-skip_update_server_mods",)

        if extra_args:
            self.logger.debug(f"传入额外参数 {extra_args}")
            cmd_list += extra_args

        if remove_server_temp:
            self._remove_server_temp()

        self._open_fd_files()
        self._process = Popen(
            cmd_list,
            stdin=PIPE,
            stdout=PIPE,
            stderr=STDOUT,  # 统一到标准输出
            cwd=self.cluster.dst_bin_path.parent,  # 需要切换工作目录
            text=True,
            encoding="utf-8",
        )

    def _read_stats(self) -> None:
        """从 fd5 读取统计数据"""
        stats_output = cast(TextIO, self._fd5_file)
        stats_raw = stats_output.readline().strip()
        stats_key, stats_value = stats_raw.split("|")
        match stats_key.lower():
            # DST_Stats|3.226599,2.355073,0.293711,3,8
            case "dst_stats":
                stats_value.split(",")
            case "dst_sessionid":
                pass
            case "dst_master_ready":
                pass
            case "dst_numplayerschanged":
                num_players = int(stats_value)
            case "dst_saved":
                data_file = Path(stats_value)
            

        

    def start(self) -> None:
        """启动分片"""
        self.logger.info(f"启动分片 {self.name}")
        self._start()

    def stop(self, save: bool = True) -> None:
        """停止分片"""
        self._stop_by_cmd(save=save)

    def restart(self) -> None:
        """重启"""
        self.logger.info(f"重启分片 {self.name}")
        self.stop()
        self._start(remove_server_temp=False)

    def update_mod(self) -> None:
        """更新 mod"""
        self.logger.info("更新 mod")
        self._start(
            skip_update_server_mods=False,
            extra_args=("-only_update_server_mods",),
        )
        self.stop()

    def _send_cmd(self, command: str) -> str:
        """发送控制台命令"""
        console_input = cast(TextIO, self._fd3_file)
        console_output = cast(TextIO, self._fd4_file)

        self.logger.debug(f"发送控制台命令 {command}")
        console_input.write(f"{command}\n")
        console_input.flush()

        lines = []
        while True:
            line = console_output.readline()
            if line.strip() == "DST_RemoteCommandDone":
                break
            else:
                lines.append(line)
        result = "".join(lines)
        log_result = result.replace("\n", r"\n")
        self.logger.debug(f"控制台输出: {log_result}")
        return result

    def _timeout_cmd(self, command: str, timeout: float) -> str:
        """发送控制台命令，超时引发异常"""
        return self._timeout_call(
            self._send_cmd,
            timeout=timeout,
            kwargs={"command": command},
        )

    def _stop_by_signal(self) -> None:
        """通过信号关闭"""
        process = cast(Popen, self._process)  # 类型注解需要转换
        try:
            process.terminate()
            process.wait(timeout=10.0)
        except TimeoutExpired:
            process.kill()
            process.wait()

    def _stop_by_cmd(self, save=True) -> None:
        """通过控制台命令关闭"""
        self._timeout_cmd(f"c_shutdown({str(save).lower()})", timeout=60.0)

    def _save(self) -> None:
        """存档"""
        self._timeout_cmd(f"c_save())", timeout=30.0)

    def _announce(self, msg: str) -> None:
        """公告"""
        self._timeout_cmd(f"c_announce({msg})", timeout=5.0)


from dataclasses import dataclass, field
from ipaddress import IPv4Address
from os import getpid
from pathlib import Path
from random import randrange
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired
from threading import Thread
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

    # 模型中默认值均来自官方文档
    # 此处提供的默认值则是开发者自行补充和调整后的默认值
    shard: ServerShardModel = ServerShardModel(is_master=True, name="[SHDMASTER]")
    steam: ServerSteamModel = ServerSteamModel()
    network: ServerNetworkModel = ServerNetworkModel()
    account: ServerAccountModel = ServerAccountModel(encode_user_path=True)


@dataclass
class Shard(ServerBase):
    """分片"""

    config_file_name: ClassVar[str] = "server.ini"

    cluster: Cluster
    stats: dict = field(default_factory=dict)
    config: ServerIniModel = field(default_factory=ServerIniModel, init=False)

    _fd3_file: Optional[TextIO] = field(default=None, init=False)
    _fd4_file: Optional[TextIO] = field(default=None, init=False)
    _fd5_file: Optional[TextIO] = field(default=None, init=False)
    _process: Optional[Popen] = field(default=None, init=False)
    _monitor_thread: Optional[Thread] = field(default=None, init=False)

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

    def _start_server(
        self,
        skip_update_server_mods: bool = True,
        remove_server_temp: bool = True,
        extra_args: Optional[Iterable[str]] = None,
    ) -> None:
        """启动服务端"""

        cmd_list = [str(self.cluster.dst_bin_path)]
        cmd_list += ("-cloudserver",)
        cmd_list += ("persistent_storage_root", str(self.cluster.data_root_path))
        cmd_list += ("-conf_dir", self.cluster.conf_dir_path.name)
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

        self._process = Popen(
            cmd_list,
            stdin=PIPE,
            stdout=PIPE,
            stderr=STDOUT,  # 统一到标准输出
            cwd=self.cluster.dst_bin_path.parent,  # 需要切换工作目录
            text=True,
            encoding="utf-8",
        )

    def _update_stats(self) -> None:
        """从 fd5 读取并更新统计数据"""
        self.logger.debug(f"分片 {self.name} 统计数据更新循环启动")
        while self.is_running():
            stats_output = cast(TextIO, self._fd5_file)
            stats_raw = stats_output.readline().strip()
            if stats_raw:
                stats_key, stats_value = stats_raw.split("|")
                match stats_key.lower():
                    case "dst_stats":
                        # DST_Stats|3.226599,2.355073,0.293711,3,8
                        (
                            cpu_load1,
                            cpu_load2,
                            unknown,
                            num_players,
                            max_players,
                        ) = stats_value.split(",")
                    case "dst_sessionid":
                        # DST_SessionId|804FE0E9FFCE345E
                        self.stats["session_id"] = stats_value
                    case "dst_master_ready":
                        # DST_Master_Ready|10999
                        self.stats["port"] = int(stats_value)
                    case "dst_numplayerschanged":
                        # DST_NumPlayersChanged|2
                        self.stats["num_players"] = int(stats_value)
                    case "dst_saved":
                        # DST_Saved|session/8B1254AC45168660/0000000033
                        self.stats["data_file"] = Path(stats_value)
                    case _:
                        self.logger.warning(f"未知统计数据 {stats_raw}")
        else:
            self.logger.debug(f"分片 {self.name} 统计数据更新循环终止")
            return

    def _monitor_stats(self) -> None:
        """监控统计数据"""
        self.logger.info(f"启动分片 {self.name} 统计数据监控线程")
        self._monitor_thread = Thread(target=self._update_stats)
        self._monitor_thread.start()

    def is_running(self) -> bool:
        """是否在运行中"""
        if self._process and not self._process.returncode:
            return True
        else:
            return False

    def start(self) -> None:
        """启动分片"""
        if not self.is_running():
            self.logger.info(f"启动分片 {self.name}")
            self.load_config()
            self._open_fd_files()
            self._start_server()
            self._monitor_stats()
        else:
            self.logger.warning(f"分片 {self.name} 已在运行态，忽略启动操作")

    def stop(self, save: bool = True) -> None:
        """停止分片"""
        if self.is_running():
            self.logger.info(f"停止分片 {self.name}")
            self._stop_by_cmd(save=save)
            cast(Thread, self._monitor_thread).join()
        else:
            self.logger.warning(f"分片 {self.name} 不在运行态，忽略停止操作")

    def update_mods(self) -> None:
        """更新 mod"""
        self.logger.info("更新 mod")
        self._start_server(
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
        self._timeout_cmd(f"c_save()", timeout=30.0)

    def _announce(self, msg: str) -> None:
        """公告"""
        self._timeout_cmd(f"c_announce(\"{msg}\")", timeout=5.0)

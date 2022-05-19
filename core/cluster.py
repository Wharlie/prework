from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from typing import ClassVar, Iterable

from pydantic import BaseModel

from ._server_base import Arch, ServerBase
from .shard import Shard


class Season(Enum):
    """TODO:季节枚举"""

    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"
    WINTER = "winter"


class Period(Enum):
    """TODO:时间段枚举"""

    DAY = "day"
    DUSK = "dusk"
    NIGHT = "night"


@dataclass
class GameTime(object):
    """TODO:游戏内时间"""

    season: Season


class ClusterIntention(Enum):
    """集群风格枚举"""

    SOCIAL = "social"
    COOPERATIVE = "cooperative"
    COMPETITIVE = "competitive"
    MADNESS = "madness"


class GameMode(Enum):
    """游戏模式枚举"""

    SURVIVAL = "survival"
    ENDLESS = "endless"
    WILDERNESS = "wilderness"


class ClusterMiscModel(BaseModel):
    """集群杂项配置模型"""

    max_snapshots: int = 6
    console_enabled: bool = True


class ClusterShardModel(BaseModel):
    """集群分片配置模型"""

    shard_enabled: bool = False
    bind_ip: IPv4Address = IPv4Address("127.0.0.1")
    master_port: int = 10888
    master_ip: IPv4Address
    cluster_key: str


class ClusterSteamModel(BaseModel):
    """集群 Steam 配置模型"""

    steam_group_only: bool = False
    steam_group_id: int = 0
    steam_group_admins: bool = False


class ClusterNetworkModel(BaseModel):
    """集群网络配置模型"""

    offline_cluster: bool = False
    tick_rate: int = 15
    whitelist_slots: int = 0
    cluster_password: str
    cluster_name: str
    cluster_description: str
    lan_only_cluster: bool = False
    cluster_intention: ClusterIntention
    autosaver_enabled: bool = True
    cluster_language: str = "en"


class ClusterGameplayModel(BaseModel):
    """集群游戏配置模型"""

    max_players: int = 16
    pvp: bool = False
    game_mode: GameMode = GameMode.SURVIVAL
    pause_when_empty: bool = False
    vote_enabled: bool = True


class ClusterIniModel(BaseModel):
    """集群配置模型（cluster.ini）"""

    misc: ClusterMiscModel
    shard: ClusterShardModel
    steam: ClusterSteamModel
    network: ClusterNetworkModel
    gameplay: ClusterGameplayModel


class Cluster(ServerBase):
    """集群"""

    shard_list: list[Shard]

    arch: Arch = Arch.amd64
    steamcmd_path: ClassVar[Path] = Path("/home/steam/steamcmd/steamcmd.sh")
    dst_install_path: ClassVar[Path] = Path("/home/steam/DST")

    data_root_path: Path = Path("/home/steam/data")
    conf_dir_name: str = "dst"
    config_file_name: ClassVar[str] = "cluster.ini"
    mods_dir_name: ClassVar[str] = "mods"
    ugc_dir_name: ClassVar[str] = "ugc"
    permission_config_file_names: ClassVar[Iterable[str]] = (
        "adminlist.txt",
        "whitelist.txt",
        "blocklist.txt",
    )

    @property
    def conf_dir_path(self) -> Path:
        return self.data_root_path / self.conf_dir_name

    @property
    def mods_path(self) -> Path:
        return self.dir_path / self.mods_dir_name

    @property
    def ugc_path(self) -> Path:
        return self.mods_path / self.ugc_dir_name

    @property
    def dst_bin_path(self) -> Path:
        match self.arch:
            case Arch.amd64:
                return (
                    self.dst_install_path
                    / "bin64"
                    / "dontstarve_dedicated_server_nullrenderer_x64"
                )
            case Arch.x86:
                return (
                    self.dst_install_path
                    / "bin"
                    / "dontstarve_dedicated_server_nullrenderer"
                )
            case _:
                err_msg = f"未知架构 {self.arch}"
                self.logger.error(err_msg)
                raise ValueError(err_msg)

    @classmethod
    def update_mods(cls) -> None:
        """更新 mod"""
        with TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            

    @classmethod
    def update_steam(cls) -> None:
        """更新 Steam"""
        cmd_list = [str(cls.steamcmd_path)]
        cmd_list += ("+@ShutdownOnFailedCommand", "0")
        cmd_list += ("+@NoPromptForPassword", "0")
        cmd_list += ("+force_install_dir", str(cls.dst_install_path))
        cmd_list += ("+login", "anonymous")
        cmd_list += ("+app_update", "343049", "validate")
        cmd_list += ("+quit",)

    def _detect_shard_paths(self) -> list[Path]:
        """检测分片文件夹路径"""
        shard_paths = []
        for child in self.dir_path.iterdir():
            if child.is_dir():
                shard_paths.append(child)
        return shard_paths

    def _complete_permission_file(self) -> None:
        """补全权限配置文件，便于后续手动修改"""
        for file_name in self.permission_config_file_names:
            file_path = self.dir_path / file_name
            file_path.touch()

        self.mods_path.mkdir(exist_ok=True)
        self.ugc_path.mkdir(exist_ok=True)
    
    def _monitor_stats(self) -> None:
        """监控 shard 的 fd5 中的统计信息"""

        
        for shard in self.shard_list:
            pass
            
        

    def update(self) -> None:
        """更新"""
        self.update_steam()
        self.update_mods()

    def _start(self) -> None:
        pass

    def _stop(self) -> None:
        pass

    def start(self) -> None:
        """启动"""
        self.load_ini()
        self.update()
        self._start()

    def stop(self) -> None:
        self._stop()

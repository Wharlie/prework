from subprocess import CalledProcessError, run
from dataclasses import dataclass, field
from enum import Enum
from ipaddress import IPv4Address
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ClassVar, Iterable

from pydantic import BaseModel

from ._server_base import ServerBase
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

    misc: ClusterMiscModel = ClusterMiscModel()
    shard: ClusterShardModel = ClusterShardModel(
        master_ip=IPv4Address("127.0.0.1"),
        cluster_key="dont_starve_together",
    )
    steam: ClusterSteamModel = ClusterSteamModel()
    network: ClusterNetworkModel = ClusterNetworkModel(
        cluster_password="",
        cluster_name="DST",
        cluster_description="Don't Starve Together",
        cluster_intention=ClusterIntention.COOPERATIVE,
    )
    gameplay: ClusterGameplayModel = ClusterGameplayModel()


@dataclass
class Cluster(ServerBase):
    """集群"""

    steamcmd_path: ClassVar[Path] = Path("/home/steam/steamcmd/steamcmd.sh")
    dst_install_path: ClassVar[Path] = Path("/home/steam/DST")
    dst_bin_path: ClassVar[Path] = Path(
        "/home/steam/DST/bin64/dontstarve_dedicated_server_nullrenderer_x64"
    )
    config_file_name: ClassVar[str] = "cluster.ini"
    ugc_dir_name: ClassVar[str] = "ugc_mods"
    permission_config_file_names: ClassVar[Iterable[str]] = (
        "adminlist.txt",
        "whitelist.txt",
        "blocklist.txt",
    )

    shard_list: list[Shard] = field(default_factory=list)

    config: ClusterIniModel = field(default_factory=ClusterIniModel, init=False)

    @property
    def data_root_path(self) -> Path:
        return self.dir_path.parents[1]

    @property
    def conf_dir_path(self) -> Path:
        return self.dir_path.parent

    @property
    def ugc_path(self) -> Path:
        return self.dst_install_path / self.ugc_dir_name

    @classmethod
    def update_mods(cls) -> None:
        """更新 mod"""
        with TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            temp_cluster = Cluster(dir_path=temp_dir_path)
            temp_shard = Shard(dir_path=temp_dir_path / "Temp", cluster=temp_cluster)
            temp_cluster.shard_list.append(temp_shard)
            temp_shard.update_mods()

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
        try:
            run(cmd_list,check=True)
        except CalledProcessError as e:
            raise RuntimeError("Steam 更新失败") from e
        

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

    def is_running(self) -> bool:
        """是否在运行中"""
        return any(shard.is_running() for shard in self.shard_list)

    def update(self) -> None:
        """更新"""
        self.logger.info("更新 steam")
        self.update_steam()
        self.logger.info("更新 mod")
        self.update_mods()

    def start(self) -> None:
        """启动"""
        if not self.is_running():
            self.load_config()
            self.update()

            if not self.shard_list:
                for shard_path in self._detect_shard_paths():
                    shard = Shard(dir_path=shard_path, cluster=self)
                    self.shard_list.append(shard)

            for shard in self.shard_list:
                shard.start()
        else:
            self.logger.warning(f"集群 {self.name} 已在运行态，忽略启动操作")

    def stop(self) -> None:
        """停止"""
        if self.is_running():
            for shard in self.shard_list:
                shard.stop()
        else:
            self.logger.warning(f"集群 {self.name} 不在运行态，忽略停止操作")

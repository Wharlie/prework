from configparser import ConfigParser as IniConfigParser
from enum import Enum
from ipaddress import IPv4Address
from pathlib import Path
from random import randrange
from typing import Type, TypeVar

from pydantic import BaseModel, Field, IPvAnyAddress, SecretStr


class ClusterIntention(Enum):
    """集群风格枚举"""

    SOCIAL: str = "social"
    COOPERATIVE: str = "cooperative"
    COMPETITIVE: str = "competitive"
    MADNESS: str = "madness"


class GameMode(Enum):
    """游戏模式枚举"""

    SURVIVAL: str = "survival"
    ENDLESS: str = "endless"
    WILDERNESS: str = "wilderness"


class ClusterMiscModel(BaseModel):
    """集群杂项配置模型"""

    max_snapshots: int = 6
    console_enabled: bool = True


class ClusterShardModel(BaseModel):
    """集群分片配置模型"""

    shard_enabled: bool = False
    bind_ip: IPvAnyAddress = IPv4Address("127.0.0.1")
    master_port: int = 10888
    master_ip: IPvAnyAddress
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
    cluster_password: SecretStr
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


class ServerShardModel(BaseModel):
    """服务端分片配置模型"""

    is_master: bool
    name: str
    id: int = Field(default_factory=lambda: randrange(2**32))


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


def _get_dst_ini_parser() -> IniConfigParser:
    """获取 DST 适配的 ini 解析器"""
    return IniConfigParser(allow_no_value=True)


IniModelType = TypeVar("IniModelType", ClusterIniModel, ServerIniModel)


def _load_ini(
    ini_path: Path, ini_model_cls: Type[IniModelType], encoding="utf-8"
) -> IniModelType:
    """加载 ini 配置"""
    ini_parser = _get_dst_ini_parser()
    with ini_path.open(mode="rt", encoding=encoding) as f:
        ini_parser.read_file(f)
    return ini_model_cls.parse_obj(ini_parser)


def _save_ini(ini_path: Path, ini: IniModelType) -> None:
    """保存 ini 配置"""
    ini_parser = _get_dst_ini_parser()
    ini_parser.read_dict(ini.dict())
    with ini_path.open(mode="wt", encoding="utf-8") as f:
        ini_parser.write(f)


def load_cluster_ini(cluster_ini_path: Path) -> ClusterIniModel:
    """加载 cluster.ini 配置"""
    return _load_ini(cluster_ini_path, ClusterIniModel)


def save_cluster_ini(cluster_ini_path: Path, cluster_ini: ClusterIniModel) -> None:
    """保存 cluster.ini 配置"""
    _save_ini(cluster_ini_path, cluster_ini)


def load_server_ini(server_ini_path: Path) -> ServerIniModel:
    """加载 server.ini 配置"""
    return _load_ini(server_ini_path, ServerIniModel)


def save_server_ini(server_ini_path: Path, server_ini: ServerIniModel) -> None:
    """保存 server.ini 配置"""
    _save_ini(server_ini_path, server_ini)

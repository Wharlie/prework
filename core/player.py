from ipaddress import IPv4Address


class Player:
    index:int
    name: str
    steam_id: str
    klei_id: str
    ip: IPv4Address
    port: int
    health:float
    sanity:float
    hunger:float

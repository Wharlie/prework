from ipaddress import IPv4Address


class Player:
    steam_id: str
    klei_id: str
    name: str
    ip: IPv4Address
    port: int
    health:float
    sanity:float
    hunger:float

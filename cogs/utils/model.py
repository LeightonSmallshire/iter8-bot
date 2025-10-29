from dataclasses import dataclass
from datetime import datetime

@dataclass
class Timeout:
    id: int
    count: int
    duration: float

@dataclass
class Log:
    id: int
    timestamp: datetime
    level: str
    message: str

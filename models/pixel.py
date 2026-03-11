from dataclasses import dataclass
from datetime import datetime

@dataclass
class Pixel:
    x: int
    y: int
    color: str

@dataclass
class PixelHistory:
    id: int
    user_id: int
    x: int
    y: int
    color: str
    created_at: datetime

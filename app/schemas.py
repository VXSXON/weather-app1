# schemas.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class WeatherRequestBase(BaseModel):
    city: str
    temperature: float
    humidity: Optional[float] = None
    description: Optional[str] = None
    windspeed: Optional[float] = None
    winddirection: Optional[float] = None
    weathercode: Optional[int] = None

class WeatherRequestCreate(WeatherRequestBase):
    pass

class WeatherRequest(WeatherRequestBase):
    id: int
    timestamp: datetime
    
    class Config:
        from_attributes = True

class WeatherResponse(WeatherRequestBase):
    timestamp: datetime
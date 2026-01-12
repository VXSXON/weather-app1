from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class WeatherRequest(Base):
    __tablename__ = "weather_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, index=True)
    temperature = Column(Float)
    humidity = Column(Float, nullable=True)
    description = Column(String, nullable=True)
    windspeed = Column(Float, nullable=True)        # <-- ЭТО ПОЛЕ
    winddirection = Column(Float, nullable=True)    # <-- ЭТО ПОЛЕ
    weathercode = Column(Integer, nullable=True)    # <-- ЭТО ПОЛЕ
    timestamp = Column(DateTime, default=datetime.utcnow)
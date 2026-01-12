from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
import requests
import os
from datetime import datetime
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import start_http_server
import time
from typing import Dict, Any

# Создаем метрики Prometheus
REQUEST_COUNT = Counter('weather_requests_total', 'Total weather requests', ['status'])
REQUEST_LATENCY = Histogram('weather_request_latency_seconds', 'Request latency in seconds')

# Создаем таблицы в базе данных
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Weather API",
    description="API для получения погоды с сохранением в базу данных и мониторингом",
    version="1.0.0"
)

# Конфигурация Open-Meteo API (бесплатно, без ключа!)
WEATHER_API_PROVIDER = os.getenv("WEATHER_API_PROVIDER", "openmeteo")
OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"

# Координаты городов
CITY_COORDINATES = {
    "moscow": {"lat": 55.7558, "lon": 37.6173},
    "london": {"lat": 51.5074, "lon": -0.1278},
    "new york": {"lat": 40.7128, "lon": -74.0060},
    "tokyo": {"lat": 35.6762, "lon": 139.6503},
    "paris": {"lat": 48.8566, "lon": 2.3522},
    "berlin": {"lat": 52.5200, "lon": 13.4050},
    "киев": {"lat": 50.4501, "lon": 30.5234},
    "санкт-петербург": {"lat": 59.9343, "lon": 30.3351},
    "сочи": {"lat": 43.5855, "lon": 39.7231},
    "казань": {"lat": 55.7961, "lon": 49.1064},
}

# Коды погоды Open-Meteo
WEATHER_CODES = {
    0: "Ясно",
    1: "В основном ясно",
    2: "Переменная облачность",
    3: "Пасмурно",
    45: "Туман",
    48: "Изморозь",
    51: "Легкая морось",
    53: "Умеренная морось",
    55: "Сильная морось",
    56: "Легкая ледяная морось",
    57: "Сильная ледяная морось",
    61: "Небольшой дождь",
    63: "Умеренный дождь",
    65: "Сильный дождь",
    66: "Легкий ледяной дождь",
    67: "Сильный ледяной дождь",
    71: "Небольшой снег",
    73: "Умеренный снег",
    75: "Сильный снег",
    77: "Снежные зерна",
    80: "Небольшие ливни",
    81: "Умеренные ливни",
    82: "Сильные ливни",
    85: "Небольшие снегопады",
    86: "Сильные снегопады",
    95: "Гроза",
    96: "Гроза с небольшим градом",
    99: "Гроза с сильным градом"
}

@app.on_event("startup")
async def startup_event():
    """Запускаем HTTP сервер для метрик Prometheus при старте приложения"""
    start_http_server(8001)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_city_coordinates(city: str) -> Dict[str, float]:
    """Получаем координаты города по его названию"""
    city_lower = city.lower().strip()
    
    # Проверяем в нашем словаре
    if city_lower in CITY_COORDINATES:
        return CITY_COORDINATES[city_lower]
    
    # Если город не найден, используем Москву по умолчанию
    return {"lat": 55.7558, "lon": 37.6173}

def get_weather_from_openmeteo(city: str) -> Dict[str, Any]:
    """Получаем погоду из Open-Meteo API"""
    try:
        # Получаем координаты города
        coords = get_city_coordinates(city)
        
        # Параметры запроса
        params = {
            'latitude': coords['lat'],
            'longitude': coords['lon'],
            'current_weather': True,
            'hourly': 'temperature_2m,relativehumidity_2m',
            'timezone': 'auto',
            'forecast_days': 1
        }
        
        # Делаем запрос к API
        response = requests.get(OPENMETEO_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Извлекаем текущую погоду
        current = data['current_weather']
        weather_code = current['weathercode']
        
        # Получаем описание погоды
        description = WEATHER_CODES.get(weather_code, "Неизвестно")
        
        # Получаем влажность из почасовых данных
        humidity = None
        if 'hourly' in data and 'relativehumidity_2m' in data['hourly']:
            humidities = data['hourly']['relativehumidity_2m']
            if humidities:
                humidity = humidities[0]
        
        return {
            'temperature': current['temperature'],
            'humidity': humidity or 50,
            'description': description,
            'windspeed': current['windspeed'],
            'winddirection': current['winddirection'],
            'weathercode': weather_code,
            'coordinates': coords
        }
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Ошибка при запросе к API погоды: {str(e)}")
    except KeyError as e:
        raise HTTPException(status_code=500, detail=f"Некорректный ответ от API: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка: {str(e)}")

# ТОЛЬКО GET ЭНДПОИНТЫ - они работают без проблем
@app.get("/weather/{city}")
async def get_weather_by_city(city: str, db: Session = Depends(get_db)):
    """GET endpoint для получения погоды"""
    start_time = time.time()
    
    try:
        weather_data = get_weather_from_openmeteo(city)
        
        # Сохраняем в БД
        db_weather = models.WeatherRequest(
            city=city,
            temperature=weather_data['temperature'],
            humidity=weather_data['humidity'],
            description=weather_data['description'],
            windspeed=weather_data.get('windspeed'),
            winddirection=weather_data.get('winddirection'),
            weathercode=weather_data.get('weathercode')
        )
        db.add(db_weather)
        db.commit()
        db.refresh(db_weather)
        
        REQUEST_COUNT.labels(status='success').inc()
        
        return {
            "city": city,
            "temperature": weather_data['temperature'],
            "humidity": weather_data['humidity'],
            "description": weather_data['description'],
            "windspeed": weather_data.get('windspeed'),
            "winddirection": weather_data.get('winddirection'),
            "weathercode": weather_data.get('weathercode'),
            "coordinates": weather_data.get('coordinates', {}),
            "provider": WEATHER_API_PROVIDER,
            "timestamp": datetime.utcnow().isoformat(),
            "id": db_weather.id
        }
        
    except HTTPException as he:
        REQUEST_COUNT.labels(status='error').inc()
        raise he
    except Exception as e:
        REQUEST_COUNT.labels(status='error').inc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        latency = time.time() - start_time
        REQUEST_LATENCY.observe(latency)

@app.get("/metrics")
async def metrics():
    """Эндпоинт для сбора метрик Prometheus"""
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.get("/history/")
async def get_history(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    """Получить историю запросов погоды"""
    history = db.query(models.WeatherRequest).order_by(models.WeatherRequest.timestamp.desc()).offset(skip).limit(limit).all()
    
    return [
        {
            "id": item.id,
            "city": item.city,
            "temperature": item.temperature,
            "humidity": item.humidity,
            "description": item.description,
            "windspeed": item.windspeed,
            "winddirection": item.winddirection,
            "weathercode": item.weathercode,
            "timestamp": item.timestamp.isoformat()
        }
        for item in history
    ]

@app.get("/weather-codes")
async def get_weather_codes():
    """Получить расшифровку кодов погоды"""
    return WEATHER_CODES

@app.get("/available-cities")
async def get_available_cities():
    """Получить список доступных городов"""
    cities = list(CITY_COORDINATES.keys())
    return {
        "available_cities": cities,
        "count": len(cities)
    }

@app.get("/health")
async def health_check():
    """Проверка здоровья приложения"""
    try:
        # Простая проверка доступности внешнего API
        response = requests.get(
            "https://api.open-meteo.com/v1/status",
            timeout=5
        )
        api_status = "healthy" if response.status_code == 200 else "unhealthy"
        
        return {
            "status": "healthy",
            "api_status": api_status,
            "provider": WEATHER_API_PROVIDER,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    except Exception:
        return {
            "status": "healthy",
            "api_status": "unreachable",
            "provider": WEATHER_API_PROVIDER,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }

@app.get("/")
async def root():
    """Корневой endpoint с информацией о API"""
    return {
        "message": "Weather API с Open-Meteo",
        "description": "Бесплатный API погоды без регистрации и ключей",
        "version": "1.0.0",
        "endpoints": {
            "get_weather": "GET /weather/{city}",
            "history": "GET /history/?skip=0&limit=10",
            "health": "GET /health",
            "metrics": "GET /metrics",
            "weather_codes": "GET /weather-codes",
            "available_cities": "GET /available-cities",
            "docs": "GET /docs"
        },
        "provider": WEATHER_API_PROVIDER
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from temperature import schemas
from temperature.models import DBTemperature
from city.models import DBCity


async def get_temperatures(db: AsyncSession) -> list[DBTemperature]:
    temperatures = await db.scalars(select(DBTemperature))
    return temperatures.all()


async def create_temperature(
    db: AsyncSession,
    temperature: schemas.TemperatureCreate,
) -> DBTemperature:
    db_temperature = DBTemperature(
        city_id=temperature.city_id,
        temperature=temperature.temperature,
        date_time=temperature.date_time,
    )

    db.add(db_temperature)
    await db.commit()
    await db.refresh(db_temperature)

    return db_temperature


async def get_temperature_by_city_id(
        db: AsyncSession, city_id: int
) -> list[DBTemperature]:
    temperatures = await db.scalars(
        select(DBTemperature).where(DBTemperature.city_id == city_id)
    )
    return temperatures.all()


async def update_temperatures(db: AsyncSession) -> list[DBTemperature] | None:
    client = httpx.AsyncClient()
    cities = await db.scalars(select(DBCity))

    for city in cities:
        response = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search?"
            f"name={city.name}&count=1"
        )
        if response.status_code == 200:
            data = response.json()
            if "results" in data and len(data["results"]) > 0:
                latitude = data["results"][0]["latitude"]
                longitude = data["results"][0]["longitude"]

                weather_results = await client.get(
                    "https://api.open-meteo.com/v1/forecast?"
                    f"latitude={latitude}&longitude={longitude}"
                    f"&current=temperature_2m"
                )
                if weather_results.status_code == 200:
                    weather_data = weather_results.json()
                    if "current" in weather_data:
                        temperature_value = (
                            weather_data["current"]["temperature_2m"]
                        )
                        db_temperature = DBTemperature(
                            city_id=city.id,
                            temperature=temperature_value,
                            date_time=weather_data["current"]["time"],
                        )
                        db.add(db_temperature)
                        await db.commit()
                        await db.refresh(db_temperature)

    await client.aclose()
    temperatures = await db.scalars(
        select(DBTemperature).order_by(DBTemperature.date_time.desc())
    )
    return temperatures.all()

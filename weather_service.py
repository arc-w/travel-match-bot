import aiohttp


async def get_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=True"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                current = data['current_weather']
                return {
                    "temp": current['temperature'],
                    "wind": current['windspeed']
                }
            return None
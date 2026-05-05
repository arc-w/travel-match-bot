import aiohttp
from datetime import datetime, timedelta


async def get_next_holiday(country_code):
    year = datetime.now().year
    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    holidays = await response.json()
                    today = datetime.now().date()

                    for h in holidays:
                        h_date = datetime.strptime(h['date'], '%Y-%m-%d').date()
                        if h_date >= today:
                            if (h_date - today).days <= 14:
                                return f"{h['localName']} ({h_date.strftime('%d.%m')})"
                            else:
                                return "brak danych"
        except Exception:
            pass

    return "brak danych"
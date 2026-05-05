import aiohttp
import urllib.parse

async def get_wikipedia_info(city_name):
    headers = {
        "User-Agent": "TravelMatchBot/1.0 (travelbot.kontakt@gmail.com) aiohttp-bot",
        "Accept": "application/json"
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            search_query = urllib.parse.quote(city_name.strip())
            search_url = f"https://pl.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_query}&format=json"
            async with session.get(search_url) as search_response:
                if search_response.status == 200:
                    search_data = await search_response.json()
                    search_results = search_data.get("query", {}).get("search", [])
                    if search_results:
                        formatted_title = search_results[0]["title"].replace(" ", "_")
                    else:
                        formatted_title = city_name.strip().replace(" ", "_")
                else:
                    formatted_title = city_name.strip().replace(" ", "_")
            query = urllib.parse.quote(formatted_title)
            summary_url = f"https://pl.wikipedia.org/api/rest_v1/page/summary/{query}"

            extract = "Brak szczegółowego opisu."
            image_url = None

            async with session.get(summary_url) as response:
                if response.status == 200:
                    data = await response.json()
                    extract = data.get("extract", extract)

                    if "thumbnail" in data:
                        image_url = data["thumbnail"]["source"]
                    if "originalimage" in data:
                        image_url = data["originalimage"]["source"]

            if not image_url:
                en_search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={search_query}&format=json"
                async with session.get(en_search_url) as en_search_response:
                    if en_search_response.status == 200:
                        en_search_data = await en_search_response.json()
                        en_search_results = en_search_data.get("query", {}).get("search", [])

                        if en_search_results:
                            en_formatted_title = en_search_results[0]["title"].replace(" ", "_")
                            en_query = urllib.parse.quote(en_formatted_title)
                            en_summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{en_query}"

                            async with session.get(en_summary_url) as en_response:
                                if en_response.status == 200:
                                    en_data = await en_response.json()
                                    if "thumbnail" in en_data:
                                        image_url = en_data["thumbnail"]["source"]
                                    if "originalimage" in en_data:
                                        image_url = en_data["originalimage"]["source"]

            return extract, image_url

        except Exception as e:
            print(f"Błąd Wikipedii: {e}")
            return None, None
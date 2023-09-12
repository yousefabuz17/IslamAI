import os
from geocoder import location
import asyncio
import aiohttp
from pprint import pprint
from zipfile import ZipFile
from pathlib import Path
import json
from nested_lookup import nested_lookup as nested

file = json.load(open(Path(__file__).parent.absolute() / 'islamic_data' / 'jsons' / 'list_of_surahs.json', mode='r', encoding='utf-8'))
a = nested('verses', file['1'])[0].keys()
pprint(a)
# async def _request(lat, long):
#     async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), raise_for_status=True) as session:
#         async with session.get(f'http://api.aladhan.com/v1/qibla/:{lat}/:{long}') as response:
#             return await response.json()

# async def main():
#     name = 'Staten Island, New York, United States'
#     Coords = namedtuple('Coords', ['lat', 'long', 'qibla'], defaults=['', '', None])
#     loc = location(name)
#     coords = Coords(lat=loc.lat, long=loc.lng)
#     print(coords.qibla)
#     pprint(await _request(*[coords.lat, coords.long]))
# asyncio.run(main())

# all_contents = {title: {toc.get(1): {**first_chap}, **{idx: value for idx,(_num, value) in enumerate(toc.items(), start=2) if _num>1}}}


import asyncio
from collections import OrderedDict
from configparser import ConfigParser
from functools import lru_cache
from pathlib import Path
from pprint import pprint
from typing import List, NamedTuple, Union

from aiohttp import ClientSession, TCPConnector
from ascii_graph import Pyasciigraph


class ConfigInfo(NamedTuple):
    quran_host: str=None
    quran_url: str=None
    quran_api: str=None
    
    @classmethod
    @lru_cache(maxsize=None)
    def get_config(cls):
        config_parser = ConfigParser(allow_no_value=True)
        config_parser.read(Path(__file__).parent.absolute() / 'config.ini')
        config = ConfigInfo(*[val for _, val in config_parser.items('Database')])
        return config
    
    @property
    def config(self):
        return self.get_config()

class QuranAPI:
    def __init__(self):
        self.config = self._get_config()
        self.url = self.config.quran_url
        self.headers = {
            "X-RapidAPI-Key": self.config.quran_api,
            "X-RapidAPI-Host": self.config.quran_host
        }

    @staticmethod
    @lru_cache(maxsize=None)
    def _get_config():
        config_parser = ConfigParser(allow_no_value=True)
        config_parser.read(Path(__file__).parent.absolute() / 'config.ini')
        return ConfigInfo(*[val for _, val in config_parser.items('Database')])

    @lru_cache(maxsize=None)
    async def _request(self, endpoint: Union[int, str], **params):
        range_ = params.get('range_', '')
        keyword = params.get('keyword', '')
        full_endpoint = '{}{}{}'.format(self.url, f'/{endpoint}/', range_ or keyword)
        
        async with ClientSession(connector=TCPConnector(ssl=False), raise_for_status=True) as session:
            async with session.get(full_endpoint, headers=self.headers) as response:
                return await response.json()

    async def parse_surah(self, surah_id: Union[int, str]=None, **params):
        endpoint = 'corpus' if surah_id is None else str(surah_id)
        range_ = params.get('range_', '')
        if range_:
            range_ = '-'.join(list(map(str, range_)))
        keyword = params.get('keyword', '')
        return await self._request(endpoint, range_=range_, keyword=keyword)
    
    @staticmethod
    def _format_stats(stats, type_: Union[dict, list, OrderedDict, None]=None, format_:int=0|1):
        if type_ in [dict, OrderedDict]:
            stats = {' '.join(key.split('_')).title(): value for key, value in stats.items()}
            new_stats = OrderedDict(sorted(stats.items(), key=lambda i: i[format_]))
            return new_stats
        elif type_==list:
            stats = [[' '.join(key.split('_')).title(), value] for key, value in stats.items()]
            stats.sort(key=lambda i: i[format_])
            return stats
        else:
            if isinstance(stats, list):
                stats = [[' '.join(key.split('_')).title(), value] for key, value in stats.items()]
                stats.sort(key=lambda i: i[format_])
                return stats
            return stats
    
    async def get_stats(self, display=False):
        stats = await self._request('')
        if display:
            stats = self._format_stats(stats, type_=list, format_=1)
            chart = Pyasciigraph(titlebar='-')
            for stat in chart.graph(label='\t\t\t\t Quran Statistics',data=stats):
                print(stat)
        return stats

    @property
    async def list_surahs(self):
        surahs = {}
        for i in range(1, 115):
            response = await self.parse_surah(i)
            surahs[response['id']] = response['surah_name']
        return surahs

async def main():
    quran_api = QuranAPI()
    surah = await quran_api.parse_surah(keyword='state')
    pprint(surah)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

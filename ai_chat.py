import asyncio
import json
import re
from collections import OrderedDict, defaultdict
from configparser import ConfigParser
from dataclasses import dataclass
from functools import lru_cache, wraps
from pathlib import Path
from pprint import pprint
from typing import NamedTuple, Union
# import rasa
import requests
from bs4 import BeautifulSoup
from aiohttp import ClientSession, TCPConnector, client_exceptions
from ascii_graph import Pyasciigraph
from nested_lookup import nested_lookup as nested
from rapidfuzz import fuzz, process
from typing import Literal, List
from unidecode import unidecode
from pydantic import BaseModel

class ConfigInfo:
    _config = None
    
    def __init__(self):
        config = self._get_config()
        for key, value in config.items():
            setattr(self, key, value)

    @classmethod
    @lru_cache(maxsize=None)
    def _get_config(cls, key='Database'):
        if cls._config is None:
            config_parser = ConfigParser()
            config_parser.read(Path(__file__).parent.absolute() / 'config.ini')
            cls._config = dict(config_parser[key])
        return cls._config

class QuranAPI:
    config = ConfigInfo()
    path = Path(__file__).parent.absolute() / 'islamic_data'
    
    def __init__(self):
        self.url = self.config.quran_url
        self.headers = {
            "X-RapidAPI-Key": self.config.quran_api,
            "X-RapidAPI-Host": self.config.quran_host
        }
    
    @lru_cache(maxsize=None)
    async def _request(self, endpoint: Union[int, str], **params):
        range_, keyword, slash, url = tuple(map(lambda i: params.get(i, ''), ('range_', 'keyword', 'slash', 'url')))
        slash = '/' if slash else ''
        full_endpoint = '{}{}{}'.format(self.url if not url else url, f'{slash+endpoint}', range_ or keyword)
        try:
            async with ClientSession(connector=TCPConnector(ssl=False), raise_for_status=True) as session:
                async with session.get(full_endpoint, headers=self.headers) as response:
                    return await response.json()
        except (client_exceptions.ContentTypeError) as e:
            return await response.text()
    
    async def parse_surah(self, surah_id: Union[int, str, None]='', **params):
        '''
        surah_id: Union[int, str, None]
        range_: List[int, int] -> str(int-int)
        keyword: /keyword
        '''
        range_, keyword = tuple(map(lambda i: params.get(i, ''), ('range_', 'keyword')))
        if range_:
            range_ = f"/{'-'.join(list(map(str, range_)))}"
        endpoint = 'corpus/' if (surah_id=='' and keyword) else str(surah_id)
        request = await self._request(endpoint, range_=range_, keyword=keyword)
        return request
    
    @classmethod
    def _format_stats(cls, stats, type_: Union[list, None]=dict, **params):
        default_values = [False, 1]
        display, format_ = tuple(params.get(key, default_values[i]) for i, key in enumerate(('display', 'format_')))
        stats['total_surahs'] = 114
        if isinstance(stats, (dict, OrderedDict)) and (not display):
            stats = {' '.join(key.split('_')).title(): value for key, value in stats.items()}
            new_stats = OrderedDict(sorted(stats.items(), key=lambda i: i[format_]))
            return new_stats
        elif (type_==list and display) or (type_==list and not display):
            stats = [[' '.join(key.split('_')).title(), value] for key, value in stats.items()]
            stats.sort(key=lambda i: i[format_])
            return stats
    
    async def get_stats(self, **params):
        stats = await self._request('')
        default_values = [False, 1]
        display, format_ = tuple(params.get(key, default_values[i]) for i, key in enumerate(('display', 'format_')))
        if display:
            stats = self._format_stats(stats, type_=list, display=True, format_=format_)
            chart = Pyasciigraph(titlebar='-')
            for stat in chart.graph(label='\t\t\t\t Quran Statistics',data=stats):
                print(stat)
        else:
            new_stats = self._format_stats(stats, type_=dict, format_=1)
            return new_stats

    
    async def _extract_surahs(self, export=False):
        surahs = {}
        for i in range(1, 115):
            response = await self.parse_surah(i)
            surahs[response['id']] = response['surah_name']
        if export:
            with open(self.path / 'list_of_surahs.json', mode='w', encoding='utf-8') as file:
                json.dump(surahs, file, indent=4)
        return surahs
    
    @classmethod
    @lru_cache(maxsize=None)
    def list_surahs(cls):
        _json_file = json.load(open(cls.path / 'list_of_surahs.json', mode='r', encoding='utf-8'))
        modified = {int(key): unidecode(re.sub(' ', '-', value)) for key, value in _json_file.items()}
        sort_json = sorted(modified.items(), key=lambda i: i[0])
        surahs = OrderedDict(sort_json)
        return surahs
    
    def best_match(self, string, **params):
        surah_names = self.list_surahs()
        values_ = params.get('values_', surah_names)
        if values_ and not isinstance(values_, (dict, OrderedDict, defaultdict)):
            values_ = {value: key for value, key in enumerate(values_)}
        match_ = process.extractOne(string.lower(), list(map(str.lower, values_.values())), scorer=fuzz.ratio)
        matched = match_[0].upper() if all(i.isupper() for i in values_.values()) else match_[0].title()
        return matched
    
    async def minimize_surah(self, **params):
        default_values = [1, 'fatiha', 'en']
        surah_id, name, lang = (params.get(key, default_values[i]) for i, key in enumerate(('surah_id', 'name', 'lang')))
        if name and not surah_id:
            name = self.best_match(name)
            ...

class HadithAPI(QuranAPI):
    def __init__(self):
        super().__init__()
        self.url = self.config.hadith_url
        self.headers = None
    
    async def _extract_urls(self, **params):
        async def _parser(contents):
            for book, link in contents.items():
                with open(self.path / f'book_{book}.json', mode='w', encoding='utf-8') as file2:
                    hadith_json = await self._request('', slash=False, url=link)
                    json.dump(hadith_json, file2, indent=4)
            return file2
        default_values = [False, Literal[True], 'English']
        parser, _, lang = (params.get(key, default_values[i]) for i,key in enumerate(('parser', 'export', 'lang')))
        json_file = await self._request('', slash=False)
        contents_ = [(nested('book', j, wild=True), nested('link', j, wild=True)) for i in json_file.values() for j in i['collection'] if j.get('language') == lang]
        contents = {key[0][0]: key[1][0] for key in contents_}
        
        if _:
            file = open(self.path / 'hadith_api_links.json', mode='w', encoding='utf-8')
            json.dump(contents, file, indent=4)
            return contents
        if parser:
            json_file = json.load(open(self.path / 'hadith_api_links.json', mode='r', encoding='utf-8'))
            await _parser(json_file)
            return contents
        else:
            return contents
        
    async def _get_hadiths(self, **params):
        return await self._extract_urls(**params)
    
    async def get_hadith(self, **params):
        contents = await self._get_hadiths(parser=True)
        book_authors = contents.keys()
        default_values = ['', False]
        author, _  = [params.get(key, default_values[i]) for i, key in enumerate(('author', ''))]
        if author:
            author = self.best_match(author, values_=book_authors)
            book_json = json.loads((self.path / f'book_{author}.json').read_text(encoding='utf-8'))
            return book_json
        else:
            return contents
    
    async def minimize_hadith(self, **params):
        ...


class IslamFacts(QuranAPI):    
    facts = set()
    def __init__(self):
        super().__init__()
        self.url = self.config.islam_facts
        self.headers = None
    
    def _request_contents(self):
        return requests.get(self.url).text
    
    def fun_fact(self, **params):
        limit = params.get('limit', 1)
        for _ in range(limit):
            html_content = self._request_contents()
            soup = BeautifulSoup(html_content, 'html.parser')
            fun_fact = soup.find_all('h2')[0].text
            formatted = re.sub(r'\((Religion > Islam )\)', '', fun_fact).strip()
            self.facts.add(formatted)
        fun_facts = dict.fromkeys(self.facts)
        file_mode = 'a' if Path(self.path / 'islam_facts.json').exists() else 'w'
        with open(self.path / 'islam_facts.json', mode=file_mode, encoding='utf-8') as file:
            json.dump(fun_facts, file, indent=4)
        return formatted
    
    @property
    def get_all_facts(self):
        return self.facts


#!> QuranAPI Class
    #?> Add display for extracted surahs after minimizing 
        #? Options to show in arabic & english side by side
        #?> Flask Class
            #? Create Flask endpoints for display
            #? Add audio


#!> Hadith Class
    #! https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions.min.json
    ...

#!> Islam Class
    #?> Fetch facts about islam religion
        #? All of Allahs names
        #? Islam Pillars
        #? https://fungenerators.com/random/facts/religion/islam

async def main():
    # a = HadithAPI()
    # pprint(await a.get_hadith(author='nasai'))
    b = IslamFacts()
    print(b.fun_fact(limit=100))
    pprint(b.get_all_facts, indent=4)
    
if __name__ == '__main__':
    asyncio.run(main())

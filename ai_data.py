import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
import asyncio
import json
import re
from collections import (OrderedDict, defaultdict)
from configparser import ConfigParser
from dataclasses import dataclass
from functools import (lru_cache, wraps)
from pathlib import Path
from pprint import pprint
from random import choice
from typing import (Literal, NamedTuple, Type, Union)

# import rasa
# import tensorflow as tf
from aiohttp import (ClientSession, TCPConnector, client_exceptions)
from ascii_graph import Pyasciigraph
from bs4 import BeautifulSoup
from nested_lookup import nested_lookup as nested
from rapidfuzz import (fuzz, process)
from transformers import (MarianConfig, MarianMTModel, MarianTokenizer, pipeline)
from unidecode import unidecode


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

class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super(SingletonMeta, cls).__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

class Translate:
    text = None
    
    @classmethod
    @lru_cache(maxsize=1)
    def _translate_text(cls, text, src_lang, tgt_lang):
        model_name = f'Helsinki-NLP/opus-mt-{src_lang}-{tgt_lang}'
        config = MarianConfig.from_pretrained(model_name, revision="main")
        model = MarianMTModel.from_pretrained(model_name, config=config)
        tokenizer = MarianTokenizer.from_pretrained(model_name, config=config)
        translation = pipeline("translation", model=model, tokenizer=tokenizer)
        translated_text = translation(text, max_length=4096, return_text=True)[0]
        cls.text = translated_text.get('translation_text')
        return translated_text.get('translation_text')

    @property
    def translate(self, *args):
        return self._translate_text(*args)

    @staticmethod
    def best_match(string, **kwargs):
        #?> Add a check ratio method
        values_ = kwargs.get('values_', ['test1', 'test2', 'test3'])
        if values_ and not isinstance(values_, (dict, OrderedDict, defaultdict)):
            values_ = {value: key for value, key in enumerate(values_)}
        match_ = process.extractOne(string.lower(), [i.lower() for i in values_.values()], scorer=fuzz.ratio)
        matched = match_[0].upper() if all(i.isupper() for i in values_.values()) else match_[0].title()
        return matched, match_

@dataclass
class BaseAPI(Translate):
    config: None=ConfigInfo()
    path: None=Path(__file__).parent.absolute() / 'islamic_data'

class QuranAPI(BaseAPI, metaclass=SingletonMeta):
    def __init__(self):
        self.url = self.config.quran_url
        self.headers = {
            "X-RapidAPI-Key": self.config.quran_api,
            "X-RapidAPI-Host": self.config.quran_host
        }
    
    async def _request(self, endpoint: Union[int, str], **kwargs):
        default_values = ['']*4 + [{}]
        range_, keyword, slash, url = tuple(kwargs.get(key, default_values[i]) for i,key in enumerate(('range_', 'keyword', 'slash', 'url')))
        slash = '/' if slash else ''
        full_endpoint = '{}{}{}'.format(self.url if not url else url, f'{slash+endpoint}', range_ or keyword)
        try:
            async with ClientSession(connector=TCPConnector(ssl=False), raise_for_status=True) as session:
                async with session.get(full_endpoint, headers=self.headers) as response:
                    return await response.json()
        except (client_exceptions.ContentTypeError):
            return await response.text()
    
    async def parse_surah(self, surah_id: Union[int, str, None]='', **kwargs):
        '''
        surah_id: Union[int, str, None]
        range_: List[int, int] -> str(int-int)
        keyword: /keyword
        '''
        range_, keyword = tuple(kwargs.get(i, '') for i in ('range_', 'keyword'))
        if range_:
            range_ = f"/{'-'.join(list(map(str, range_)))}"
        endpoint = 'corpus/' if (not surah_id and keyword) else str(surah_id)
        request = await self._request(endpoint, range_=range_, keyword=keyword, slash=True)
        return request
    
    @staticmethod
    def _format_stats(stats, type_: Union[list, None]=dict, **kwargs):
        default_values = (False, 1)
        display, format_ = tuple(kwargs.get(key, default_values[i]) for i, key in enumerate(('display', 'format_')))
        stats['total_surahs'] = 114
        if isinstance(stats, (dict, OrderedDict)) and (not display):
            stats = {' '.join(key.split('_')).title(): value for key, value in stats.items()}
            new_stats = OrderedDict(sorted(stats.items(), key=lambda i: i[format_]))
            return new_stats
        elif (type_==list and display) or (type_==list and not display):
            stats = [[' '.join(key.split('_')).title(), value] for key, value in stats.items()]
            stats.sort(key=lambda i: i[format_])
            return stats

    async def get_stats(self, **kwargs):
        stats = await self._request('', **kwargs)
        default_values = (False, 1)
        display, format_ = tuple(kwargs.get(key, default_values[i]) for i, key in enumerate(('display', 'format_')))
        try:
            if display:
                stats = self._format_stats(stats, type_=list, display=True, format_=format_)
                chart = Pyasciigraph(titlebar='-')
                for stat in chart.graph(label='\t\t\t\t Quran Statistics',data=stats):
                    print(stat)
            else:
                new_stats = self._format_stats(stats, type_=dict, format_=1)
                return new_stats
        except (AttributeError) as e:
            print('Modify \'Pyasciigraph\' module!\n Change all \'collections.abc.Iterable\' -> collections.abc.Iterable')

    async def _extract_surahs(self, export=False):
        surahs = {}
        for i in range(1, 115):
            response = await self.parse_surah(i)
            surahs[response.pop('id')] = response
        if export:
            with open(self.path / 'list_of_surahs.json', mode='w', encoding='utf-8') as file:
                json.dump(surahs, file, indent=4)
        return surahs
    
    @staticmethod
    @classmethod
    @lru_cache(maxsize=1)
    def _list_surahs(cls):
        _json_file = cls._load_file(path=cls.path, name='list_of_surahs', mode='r')
        modified = {int(key): unidecode(re.sub(' ', '-', value['surah_name'])) for key, value in _json_file.items()}
        sort_json = sorted(modified.items(), key=lambda i: i[0])
        surahs = OrderedDict(sort_json)
        return surahs
    
    # async def minimize_surah(self, **kwargs):
    #     default_values = (1, 'fatiha', 'en')
    #     surah_id, name, lang = (kwargs.get(key, default_values[i]) for i, key in enumerate(('surah_id', 'name', 'lang')))
    #     if name and not surah_id:
    #         name = self.best_match(name)
    #         ...
    
    @lru_cache(maxsize=1)
    @staticmethod
    def _load_file(path, name, mode='r', encoding='utf-8', type_='json'):
        #!> Modify for flexibility
        return json.load(open(path / f'{name}.{type_}', mode=mode, encoding=encoding))

class HadithAPI(QuranAPI):
    def __init__(self):
        super().__init__()
        self.url = self.config.hadith_url
        self.headers = None

    async def _extract_urls(self, **kwargs):
        async def _parser(contents):
            for book, link in contents.items():
                with open(self.path / f'book_{book}.json', mode='w', encoding='utf-8') as file2:
                    hadith_json = await self._request('', slash=False, url=link)
                    json.dump(hadith_json, file2, indent=4)
            return file2
        default_values = (False, Literal[True], 'English')
        parser, _, lang = (kwargs.get(key, default_values[i]) for i,key in enumerate(('parser', 'export', 'lang')))
        json_file = await self._request('', slash=False, url=self.url)
        contents_ = [(nested('book', j, wild=True), nested('link', j, wild=True)) for i in json_file.values() for j in i['collection'] if j.get('language') == lang]
        contents = {key[0][0]: key[1][0] for key in contents_}
        
        if _:
            file = open(self.path / 'hadith_api_links.json', mode='w', encoding='utf-8')
            json.dump(contents, file, indent=4)
            return contents
        if parser:
            json_file = self._load_file(path=self.path, name='hadith_api_links', mode='r')
            await _parser(json_file)
            return contents
        else:
            return contents
        
    async def _get_hadiths(self, **kwargs):
        return await self._extract_urls(**kwargs)
    
    async def get_hadith(self, **kwargs):
        contents = await self._get_hadiths(parser=True)
        book_authors = contents.keys()
        default_values = ['', False]
        author, _  = [kwargs.get(key, default_values[i]) for i, key in enumerate(('author', ''))]
        if author:
            author = self.best_match(author, values_=book_authors)[0]
            book_json = json.loads((self.path / f'book_{author}.json').read_text(encoding='utf-8'))
            return book_json
        else:
            return contents
    
    async def minimize_hadith(self, **kwargs):
        ...


class IslamFacts(QuranAPI):
    facts = set()
    allah_names = dict()
    
    def __init__(self):
        super().__init__()
        self.url = BaseAPI.config
        self.headers = None
    
    @classmethod
    def _update_facts(cls, facts: set):
        file2 = cls._load_file(path=cls.path, name='islam_facts', mode='r')
        fun_facts = dict.fromkeys(file2)
        fun_facts.update(facts)
        cls.facts.update(facts)
        file3 = open(cls.path / 'islam_facts.json', mode='w', encoding='utf-8')
        json.dump(fun_facts, file3, indent=4)
        return fun_facts
    
    @staticmethod
    def _randomizer(dict_):
        new_dict = tuple(dict_.keys())
        rand_fact = choice(new_dict)
        return rand_fact
    
    async def fun_fact(self, **kwargs):
        limit = kwargs.get('limit', 2)
        formatted = ''
        if len(self.facts) == 0:
            #!> FunFact generator website only allows ~18 free SAME random facts
            while len(self.facts) <= 18:
                for _ in range(limit):
                    html_content = await self._request('', slash=False, url=self.url.islam_facts)
                    soup = BeautifulSoup(html_content, 'html.parser')
                    fun_fact = soup.find_all('h2')[0].text
                    formatted = re.sub(r'\((Religion > Islam )\)', '', fun_fact).strip()
                    self.facts.add(formatted)
        fun_facts = dict.fromkeys(self.facts)
        if not Path(self.path / 'islamic_facts.json').exists():
            with open(self.path / 'islam_facts.json', mode='w', encoding='utf-8') as file1:
                json.dump(fun_facts, file1, indent=4)
            rand_fact = self._randomizer(fun_facts)
            return rand_fact
        else:
            new_facts = self._update_facts(fun_facts)
            rand_fact = self._randomizer(new_facts)
            return rand_fact
    
    async def _extract_contents(self, **kwargs):
        default_values = ['']*3+[False, self.url.myislam]
        endpoint, class_, tag_, slash, url = tuple(kwargs.get(key, default_values[i]) for i,key in enumerate(('endpoint', 'class_', 'tag_', 'slash', 'url',)))
        main_page = await self._request(endpoint=endpoint, slash=slash, url=url)
        soup = BeautifulSoup(main_page, 'html.parser')
        params = {}
        if (class_) and not (tag_):
            params['class_'] = class_
            contents = soup.find_all(**params)
        if (tag_):
            params['tag_'] = tag_
            contents = soup.find_all(params.get(tag_, 'p'))
        
        if (tag_ and class_):
            params['class_'] = class_
            params['tag_'] = tag_
            contents = soup.find_all(params.get(tag_, 'p'), **params)
        return contents
    
    async def _allah_99names(cls, contents):
        all_names = {idx: key for idx, key in enumerate([i.text for i in contents], start=1)}
        cls.allah_names = all_names
        return all_names
    
    async def _get_name_contents(self, export=False):
        async def extract_content(**kwargs):
            return await self._extract_contents(**kwargs)
        
        def extract_name_data(html_contents):
            #? Arabic encoding [\u0600-\u06FF]
            summary = sorted(''.join([i.text for i in html_contents[3]]).split('\n'), key=len, reverse=True)[0]
            # transliteration_ar = [i for i in summary.split() if 75<=self.best_match(i[3:], values_={key:value[3:] for key,value in names.items()})[1][1]<=100]
            # t = [[i[0], i[1]] for i in transliteration_ar]
            # print(summary)
            # print(transliteration_ar)
            contents = {
                'transliteration_eng': re.sub(r'[()]', '', html_contents[0][0].text),
                'transliteration_ar': '',
                'description': [i.text for i in html_contents[1]],
                'mentions-from-quran-hadith': [i.text for i in html_contents[2]],
                'summary': summary
            }
            modified_contents = {key: ''.join(value) for key,value in contents.items()}
            return modified_contents
        main_page = await extract_content(endpoint='', slash=False, url=self.url.myislam, class_='transliteration')
        names = await self._allah_99names(main_page)
        all_name_contents = {}
        filter_names = [i.lower().replace("'", '') for i in names.values()]
        all_names = tuple(map(lambda i: i.translate(''.maketrans('dh',' z')).lstrip() if i.startswith('d') else i, filter_names))
        for name in all_names:
            html_contents = await asyncio.gather(
                            *[extract_content(endpoint=name, slash=True, class_=i) for i in ('name-meaning', 'summary', 'column-section', 'second-section')]
                            )
            all_name_contents[name] = extract_name_data(html_contents)
        # if export:
        #     with open(self.path / 'list_allah_names.json', mode='w', encoding='utf-8') as file:
        #         json.dump(all_names, file, indent=4)
        return all_name_contents
    
    @classmethod
    @property
    def allah_99names(cls):
        #!> Add Exception Handling if None
        return cls.allah_names
    
    @classmethod
    @property
    def get_all_facts(cls):
        return cls.facts

#!> QuranAPI Class
    #?> Add display for extracted surahs after minimizing 
        #? Options to show in arabic & english side by side
        #?> Flask Class
            #? Create Flask endpoints for display
            #? Add audio
    #!> Modify and use 'translation_eng' values using selenium off authentic website


#!> Hadith Class
    #! https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions.min.json
    ...

#!> Islam Class
    #?> Fetch facts about islam religion
        #? All of Allahs names
        #? Islam Pillars
        #? https://fungenerators.com/random/facts/religion/islam

async def main():
    a = QuranAPI()
    b = HadithAPI()
    c = IslamFacts()
    d = await c._get_name_contents()
    # print(d)
    # pprint(nested('transliteration_ar', d, wild=True))
    
if __name__ == '__main__':
    asyncio.run(main())

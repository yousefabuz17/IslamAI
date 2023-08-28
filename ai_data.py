import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
import asyncio
import json
import re
import threading
from collections import OrderedDict
from configparser import ConfigParser
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from pprint import pprint
from random import choice
from time import time
from typing import Literal, Union
from pdfminer.high_level import extract_pages
# import rasa
import tensorflow as tf
from aiohttp import (ClientSession, TCPConnector, client_exceptions)
from ascii_graph import Pyasciigraph
from bs4 import BeautifulSoup
from nested_lookup import nested_lookup as nested
from rapidfuzz import (fuzz, process)
from tqdm import tqdm
from transformers import MarianConfig, MarianMTModel, MarianTokenizer, pipeline
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
    _lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super(SingletonMeta, cls).__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]

class Translate:
    
    @classmethod
    @lru_cache(maxsize=1)
    def _translate_text(cls, *args):
        text, src_lang, tgt_lang = args
        model_name = f'Helsinki-NLP/opus-mt-{src_lang}-{tgt_lang}'
        config = MarianConfig.from_pretrained(model_name, revision="main")
        model = MarianMTModel.from_pretrained(model_name, config=config)
        tokenizer = MarianTokenizer.from_pretrained(model_name, config=config)
        translation = pipeline("translation", model=model, tokenizer=tokenizer)
        translated_text = translation(text, max_length=512, return_text=True)[0]
        return translated_text.get('translation_text')

    def translate(self, *args):
        return self._translate_text(*args)

    @staticmethod
    def best_match(string, **kwargs):
        #?> Add a check ratio method
        values_ = kwargs.get('values_', ['test1', 'test2', 'test3'])
        if values_ and not isinstance(values_, (dict, OrderedDict)):
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
        self.url = self.config
        self.headers = {
            "X-RapidAPI-Key": self.config.quran_api,
            "X-RapidAPI-Host": self.config.quran_host
        }
    
    async def _request(self, endpoint: Union[int, str], headers=None, **kwargs):
        default_values = ['']*4 + [{}]
        range_, keyword, slash, url = tuple(kwargs.get(key, default_values[i]) for i,key in enumerate(('range_', 'keyword', 'slash', 'url')))
        slash = '/' if slash else ''
        headers = self.headers if not None else headers
        main_url = self.url.quran_url if not url else url
        full_endpoint = '{}{}{}'.format(main_url, f'{slash+endpoint}', range_ or keyword)
        try:
            async with ClientSession(connector=TCPConnector(ssl=False), raise_for_status=True) as session:
                async with session.get(full_endpoint, headers=headers) as response:
                    return await response.json()
        except (client_exceptions.ContentTypeError):
            return await response.text()
    
    async def _parse_surah(self, surah_id: Union[int, str, None]='', **kwargs):
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
            print('Modify \'Pyasciigraph\' module!\n Change all \'collections.Iterable\' -> collections.abc.Iterable')
    
    async def _extract_surahs(self, export=False):
        async def _fix_surah_contents():
            async def _parse_myislam(name):
                main_response = await self._request(endpoint='quran-transliteration', slash=True, url=self.url.myislam, headers=None)
                soup = BeautifulSoup(main_response, 'html.parser')
                parsed_links = [re.search(r'<a\s+href="([^"]+)">', str(i)).group() for i in soup.find_all('a') if re.search(r'<a\s+href="([^"]+)">', str(i))]
                all_endpoints = [i[:-3].split('/')[-1] for i in parsed_links if re.findall(r'at|surah\-\w+\-?\w+?', i)][2:-2]
                string = process.extractOne(name.lower(), all_endpoints, scorer=fuzz.ratio)[0]
                new_response = await self._request(endpoint=string, slash=True, url=self.url.myislam, headers=None)
                soup_ = BeautifulSoup(new_response, 'html.parser')
                reverse_nums = [i.text for i in soup_.find_all('a', class_='ayat-number-style')]
                ayat_nums = sorted([':'.join(i.split(':')[::-1]) for i in reverse_nums], key=lambda i: int(i.split(':')[0]))
                main_ = [soup_.find_all('div', class_=f'translation-style translation-{i}', limit=len(ayat_nums)+1) for i in range(1, len(ayat_nums)+1)]
                main = [j.text.replace('\n',' ') for i in main_ for j in i]
                #** {Author: ''}
                all_authors = dict.fromkeys(['Yusuf Ali', 'Abul Ala Maududi', 'Muhsin Khan', 'Pickthall', 'Dr. Ghali', 'Abdul Haleem', 'Sahih International'], '')
                pattern = '|'.join(re.escape(k) for k in all_authors.keys())
                contents = [j.split(':', 1) for _, j in enumerate(main) if re.search(pattern, j)]
                for _, i in enumerate(contents):
                    for name, _ in all_authors.items():
                        if i[0]==name:
                            all_authors[name] += f'{i[1]}\n'
                all_contents = {key: value.split('\n')[:-1] for key, value in all_authors.items()}
                enum_param = 1 if ayat_nums[0][-1]=='1' else 0
                for _, (name, info) in enumerate(all_contents.items()):
                    if len(info) == len(ayat_nums):
                        data = {}
                        for idx_, (id_, text, translit, cont) in enumerate(zip(ayat_nums, info, transliteration, content), start=enum_param):
                            translation_ar, translit = ('', '') if name != 'Sahih International' else map(''.join, (cont, translit))
                            #?> Add translations here for each verse
                            data[idx_] = {'id': id_,
                                        'translation_eng': text.lstrip(),
                                        'transliteration': translit,
                                        'translation_ar': translation_ar}
                        all_contents[name] = data
                return all_contents
            
            name = response['surah_name']
            response['surah_name_ar'] = response['surah_name_ar'][::-1]
            transliteration, content = zip(*[(j['transliteration'], j['content'][::-1]) for _, j in response['verses'].items()])
            myislam_contents = await _parse_myislam(name)
            
            def _merge_all():
                modified_dict = {
                    **response,
                    'full_surah_ar': content,
                    'full_surah_en': transliteration,
                    'verses': {**myislam_contents}
                }
                return modified_dict
            updated_contents = _merge_all()
            return updated_contents
        
        surahs = {}
        for i in tqdm(range(1, 115), desc='Processing Surahs', colour='green', unit='MB'):
            response = await self._parse_surah(i)
            all_contents = await _fix_surah_contents()
            surahs[response.pop('id')] = all_contents
        if export:
            with open(self.path / 'list_of_surahs.json', mode='w', encoding='utf-8') as file:
                json.dump(surahs, file, indent=4)
        return surahs

    @classmethod
    def get_surah(cls, surah_id: str=None):
        list_surahs, _json_file = cls._list_surahs()
        if surah_id is None:
            pprint(list_surahs)
            return 'Choose a surah ID'
        else:
            surah_id = str(surah_id)
            return _json_file[surah_id]
    
    @classmethod
    def _list_surahs(cls):
        _json_file = cls._load_file(path=cls.path, name='list_of_surahs', mode='r')
        modified = {int(key): unidecode(re.sub(' ', '-', value['surah_name'])) for key, value in _json_file.items()}
        sort_json = sorted(modified.items(), key=lambda i: i[0])
        surahs = OrderedDict(sort_json)
        return surahs, _json_file
    
    @lru_cache(maxsize=1)
    @staticmethod
    def _load_file(path, name, mode='r', encoding='utf-8', type_='json'):
        #!> Modify for flexibility
        return json.load(open(path / f'{name}.{type_}', mode=mode, encoding=encoding))
    
    @classmethod
    def get_instance(cls):
        return cls()

class HadithAPI(QuranAPI):
    def __init__(self):
        super().__init__()
        self.url = self.config
        self.headers = None

    async def _extract_urls(self, **kwargs):
        async def _parser(contents):
            for book, link in tqdm(contents.items(), total=len(contents), desc='Processing Hadiths', colour='green', unit='MB'):
                with open(self.path / f'book_{book}.json', mode='w', encoding='utf-8') as file2:
                    hadith_json = await self._request('', slash=False, url=link)
                    json.dump(hadith_json, file2, indent=4)
            return file2
        default_values = (False, Literal[True], 'English')
        parser, _, lang = (kwargs.get(key, default_values[i]) for i,key in enumerate(('parser', 'export', 'lang')))
        json_file = await self._request('', slash=False, url=self.url.hadith_url)
        contents_ = [(nested('book', j, wild=True), nested('link', j, wild=True)) for i in json_file.values() for j in i['collection'] if j.get('language') == lang]
        contents = {key[0][0]: key[1][0] for key in contents_}
        path = Path(deepcopy(self.path))
        file = open(path / 'hadith_api_links.json', mode='w', encoding='utf-8')
        json.dump(contents, file, indent=4)
        file.close()
        if parser:
            json_file = json.load(open(path / 'hadith_api_links.json', encoding='utf-8'))
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

class IslamFacts(QuranAPI):
    facts = set()
    allah_names = dict()
    
    def __init__(self):
        super().__init__()
        self.url = self.config
        self.headers = None
    
    @classmethod
    def _update_facts(cls, facts: set):
        file2 = cls._load_file(path=cls.path, name='islam_facts', mode='r')
        fun_facts = dict.fromkeys(file2)
        fun_facts.update(facts)
        cls.facts.update(facts)
        file3 = open(cls.path / 'islam_facts.json', mode='w', encoding='utf-8')
        json.dump(fun_facts, file3, indent=4)
        file3.close()
        return fun_facts
    
    @staticmethod
    def _randomizer(dict_):
        #?>Modify for more flexibily to show a random content for each method
        new_dict = tuple(dict_.keys())
        rand_fact = choice(new_dict)
        # pprint(f'Random fact about Islam:\n{rand_fact}')
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
        # print('All fun facts parsed and saved')
        fun_facts = dict.fromkeys(self.facts)
        if not Path(self.path / 'islamic_facts.json').is_file():
            with open(self.path / 'islam_facts.json', mode='w', encoding='utf-8') as file1:
                json.dump(fun_facts, file1, indent=4)
            rand_fact = self._randomizer(fun_facts)
            return rand_fact
        else:
            new_facts = self._update_facts(fun_facts)
            rand_fact = self._randomizer(new_facts)
            return rand_fact
    
    async def _extract_contents(self, **kwargs):
        default_values = ['']*2+['99-names-of-allah', True, self.url.myislam]
        class_, tag_, endpoint, slash, url = tuple(kwargs.get(key, default_values[i]) for i,key in enumerate(('class_', 'tag_', 'endpoint', 'slash', 'url',)))
        main_page = await self._request(endpoint=endpoint, slash=slash, url=url)
        soup = BeautifulSoup(main_page, 'html.parser')
        params = {}
        if (class_) and (not tag_):
            params['class_'] = class_
            contents = soup.find_all(**params)
            return contents
        if (tag_):
            params['tag_'] = tag_
            contents = soup.find_all(tag_)
            return contents
        if (tag_ and class_):
            params['class_'] = class_
            contents = soup.find_all(tag_, **params)
            return contents
        return soup
    
    async def _get_name_contents(self):
        async def extract_content(**kwargs):
            return await self._extract_contents(**kwargs)
        
        async def _get_ar_names():
            return [i.text[::-1].strip('\n') for i in allah_names_html][1::4]
        
        async def _allah_99names():
            all_names = {idx: key for idx, key in enumerate([i.text for i in main_page], start=1)}
            return all_names
        
        def _fixer(undo=False):
            if not undo:
                return tuple(map(lambda i: i.translate(''.maketrans('dh',' z')).lstrip() if i.startswith('d') else i, filter_names))
            return names_copied
        
        def _extract_name_data():
            #? Arabic encoding \b[\u0600-\u06FF]+\b
            #?                 \b[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+\b
            summary_ = sorted(''.join([i.text for i in html_contents[3]]).split('\n'), key=len, reverse=True)[0]
            summary = ' '.join([i.strip('();,.')[::-1] if re.findall(r'[();,.]', i) and re.findall(r'\b[\u0600-\u06FF]+\b',i) else i for i in summary_.split()])
            contents = {
                'transliteration_eng': re.sub(r'[()]', '', html_contents[0][0].text),
                'transliteration_ar': all_ar_names[ar_name_idx],
                'description': [i.text for i in html_contents[1]],
                'mentions-from-quran-hadith': [i.text for i in html_contents[2]],
                'summary': summary
            }
            modified_contents = {key: ''.join(value) for key,value in contents.items()}
            return modified_contents
        
        main_page, allah_names_html = await asyncio.gather(
            extract_content(endpoint='99-names-of-allah', slash=True, url=self.url.myislam, class_='transliteration'),
            extract_content(endpoint='', slash=False, url=self.url.allah_names, tag_='td', class_='cb-arabic')
        )
        all_en_names, all_ar_names = await asyncio.gather(
            _allah_99names(),
            _get_ar_names()
        )
        self.allah_names = deepcopy(all_en_names)
        filter_names = [i.lower().replace("'", '') for i in all_en_names.values()]
        names_copied = list(all_en_names.values())
        all_names = _fixer(False)
        all_name_contents = {}
        for ar_name_idx, name in enumerate(all_names):
            html_contents = await asyncio.gather(
                            *[extract_content(endpoint=name, slash=True, class_=i) for i in ('name-meaning', 'summary', 'column-section', 'second-section')]
                            )
            org_names = _fixer(True)
            all_name_contents[org_names[ar_name_idx]] = _extract_name_data()
        return all_name_contents
    
    async def extract_allah_contents(self, export=False):
        all_contents = await self._get_name_contents()
        merged_contents = {}
        for idx, (name, information) in tqdm(enumerate(all_contents.items(), start=1), total=len(all_contents), desc='Processing Names of Allah', colour='green', unit='MB'):
            merged_contents[idx] = {'Name': name,
                                    'Information': {**information}}
        if export:
            with open(self.path / 'list_allah_names.json', mode='w', encoding='utf-8') as file:
                json.dump(merged_contents, file, indent=4)
        return merged_contents
    
    @classmethod
    @property
    def allah_99names(cls):
        #!> Add Exception Handling if None
        return cls.allah_names
    
    @classmethod
    @property
    def get_all_facts(cls):
        return cls.facts

async def main():
    a = QuranAPI()
    b = HadithAPI()
    c = IslamFacts()
    
    async def run_all():
        tasks = [asyncio.create_task(task) for task in [
                a._extract_surahs(export=True),
                b.get_hadith(parser=True),
                c.extract_allah_contents(export=True),
                c.fun_fact(limit=18)
                ]]
        results = await asyncio.gather(*tasks)
        return results
    
    start = time()
    await run_all()
    end = time()
    timer = (end-start)
    minutes, seconds = divmod(timer, 60) 
    print(f"Execution Time: {minutes:.0f} minutes and {seconds:.0f} seconds")

if __name__ == '__main__':
    asyncio.run(main())

import asyncio
import json
import re
import threading
from collections import (OrderedDict, namedtuple)
from concurrent.futures import ThreadPoolExecutor
from configparser import ConfigParser
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from multiprocessing import cpu_count
from pathlib import Path
from pprint import pprint
from random import choice
from time import time
from typing import Literal, Union

from aiohttp import (ClientSession, TCPConnector, client_exceptions)
from ascii_graph import Pyasciigraph
from bs4 import BeautifulSoup
from docx import Document
from geocoder import location
from nested_lookup import nested_lookup as nested
from pdfminer.high_level import extract_pages
from rapidfuzz import (fuzz, process)
from tqdm import tqdm
from unidecode import unidecode
from string import ascii_lowercase
# import tracemalloc

'''
IslamAI - Data Collection Module

This file, ai_data.py, serves as the backbone of my `IslamAI` project's data collection process.
It houses a diverse set of structured classes, each tailored to interact with specific, authentic data sources.
While these classes won't directly participate in the core functionality of my program, they play a crucial role in gathering and organizing data.

My comprehensive toolset includes asynchronous data fetching, text processing, and even advanced string matching algorithms.
Employs multi-threading for efficiency, ensuring that data retrieval remains swift and scalable.
The configuration and caching mechanisms optimize performance, while the progress tracking with tqdm keeps us informed of the process.

Notes:
    ~ It's worth noting that the inclusion of tqdm serves as a temporary debugging aid to track the process's progress.
    ~ tqdm slows the extraction process
    ~ Did not leave any memorable comments for help. File is not for showcasing.

This file stands as a testament to the unwavering commitment of both myself and all collaborators and contributors involved.
It signifies the first step towards building a robust and intelligent system for our users.

All data parsed at once average time:
    ~5-6 minutes
'''

class ConfigInfo:
    _config = None
    
    def __init__(self, key):
        config = self._get_config(key)
        for key, value in config.items():
            setattr(self, key, value)

    @classmethod
    @lru_cache(maxsize=1)
    def _get_config(cls, key='Database'):
        config_parser = ConfigParser()
        config_parser.read(Path(__file__).parent.absolute() / 'config.ini')
        config = dict(config_parser[key])
        if cls._config is None:
            cls._config = config
        return config

class SingletonMeta(type):
    _instances = {}
    _lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super(SingletonMeta, cls).__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]

@dataclass
class BaseAPI(metaclass=SingletonMeta):
    '''Class for flexible methods'''
    config: None=ConfigInfo('Database')
    path: None=Path(__file__).parent.absolute() / 'islamic_data'
    
    @staticmethod
    def best_match(string, **kwargs):
        #?> Add a check ratio method
        values_ = kwargs.get('values_', ['test1', 'test2', 'test3'])
        if values_ and not isinstance(values_, (dict, OrderedDict)):
            values_ = {value: key for value, key in enumerate(values_)}
        match_ = process.extractOne(string.lower(), [i.lower() for i in values_.values()], scorer=fuzz.ratio)
        matched = match_[0].upper() if all(i.isupper() for i in values_.values()) else match_[0].title()
        return matched, match_
    
    @staticmethod
    def _get_file(path, file_name, type_='pdfs', mode='rb', ext='pdf'):
        file = open(path / type_ / f'{file_name}.{ext}', mode=mode)
        return file
    
    @staticmethod
    def _extractor(pdf, **kwargs):
        #^ PDF Files only
        '''
        :pdf: PDF file name as str
        :kwargs: maxpages, page_numbers -> range(start,end)
        '''
        default_values = (0, None)
        maxpages, page_numbers = tuple(kwargs.get(key, default_values[i]) for i, key in enumerate(('maxpages', 'page_numbers')))
        if kwargs:
            pdf_file = extract_pages(pdf, maxpages=maxpages, page_numbers=page_numbers)
            clean_pdf = ''.join([j.get_text() for i in pdf_file for j in i if hasattr(j, 'get_text')]).split('\n')
            return clean_pdf
        else:
            pdf_file = extract_pages(pdf)
            clean_pdf = ''.join([j.get_text() for i in pdf_file for j in i if hasattr(j, 'get_text')]).split('\n')
            return clean_pdf
    
    def _get_page(self, file, start=None, end=None):
        return self._extractor(file, maxpages=start) if not end else self._extractor(file, page_numbers=range(start,end))
    
    @lru_cache(maxsize=1)
    @staticmethod
    def _load_file(path, name, mode='r', encoding='utf-8', type_='json', folder='jsons'):
        #!> Modify for flexibility
        return json.load(open(path / folder / f'{name}.{type_}', mode=mode, encoding=encoding))
    
    @classmethod
    def _exporter(cls, contents, name, e_string=False):
        with open(cls.path / 'jsons' / f'{name}.json', mode='w', encoding='utf-8') as file:
            json.dump(contents, file, indent=4, ensure_ascii=False)

class QuranAPI(BaseAPI):
    def __init__(self):
        self.url = self.config
        self.headers = {
            "X-RapidAPI-Key": self.config.quran_api,
            "X-RapidAPI-Host": self.config.quran_host
        }
    
    async def _request(self, endpoint: Union[int, str], **kwargs):
        '''range_, keyword, slash, url, headers'''
        default_values = ['']*4 + [{}]
        range_, keyword, slash, url, headers = tuple(kwargs.get(key, default_values[i]) for i,key in enumerate(('range_', 'keyword', 'slash', 'url', 'headers')))
        slash = '/' if slash else ''
        headers = self.headers if headers is None else headers
        main_url = self.url.quran_url if not url else url
        full_endpoint = '{}{}{}'.format(main_url, f'{slash+endpoint}', range_ or keyword)
        try:
            async with ClientSession(connector=TCPConnector(ssl=False, enable_cleanup_closed=True,
                                                            force_close=True, ttl_dns_cache=300),
                                    raise_for_status=True,
                                    headers=headers) as session:
                async with session.get(full_endpoint) as response:
                    return await response.json()
        except (client_exceptions.ContentTypeError):
            return await response.text()
        except (client_exceptions.ServerDisconnectedError):
            return ''
    
    async def _parse_surah(self, surahID: Union[int, str, None]='', **kwargs):
        '''
        surahID: Union[int, str, None]
        range_: List[int, int] -> str(int-int)
        keyword: /keyword
        '''
        range_, keyword = tuple(kwargs.get(i, '') for i in ('range_', 'keyword'))
        if range_:
            range_ = f"/{'-'.join(list(map(str, range_)))}"
        endpoint = 'corpus/' if (not surahID and keyword) else str(surahID)
        request = await self._request(endpoint=endpoint, headers=self.headers, range_=range_, keyword=keyword, slash=True)
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
        stats = await self._request(endpoint='', headers=self.headers)
        updated_stats = self._format_stats(stats, type_=dict)
        default_values = (False, 1, False)
        display, format_, export = tuple(kwargs.get(key, default_values[i]) for i, key in enumerate(('display', 'format_', 'export')))
        try:
            if display:
                stats = self._format_stats(stats, type_=list, display=True, format_=format_)
                chart = Pyasciigraph(titlebar='-')
                for stat in chart.graph(label='\t\t\t\t Quran Statistics',data=stats):
                    print(stat)
            if export:
                return self._exporter(updated_stats, 'quran_stats')
            else:
                new_stats = self._format_stats(stats, type_=dict, format_=1)
                return new_stats
        except (AttributeError) as e:
            print('Modify \'Pyasciigraph\' module!\n Change all \'collections.Iterable\' -> \'collections.abc.Iterable\'')
    
    async def extract_surahs(self, export=False):
        async def _fix_surah_contents():
            async def _parse_myislam(surahID):
                soup = await self._extract_contents(endpoint='quran-transliteration', slash=True, url=self.url.myislam, headers=None)
                parsed_links = [re.search(r'<a\s+href="([^"]+)">', str(i)).group() for i in soup.find_all('a') if re.search(r'<a\s+href="([^"]+)">', str(i))]
                main_endpoints = [i[:-3].split('/')[-1] for i in parsed_links if re.findall(r'at|surah\-\w+\-?\w+?', i)][2:-2]
                all_endpoints = {idx: key for idx,key in enumerate(main_endpoints, start=1)}
                surah_endpoint = all_endpoints.get(surahID)
                soup_ = await self._extract_contents(endpoint=surah_endpoint, slash=True, url=self.url.myislam, headers=None)
                ayat_nums = [i.text for i in soup_.find_all('a', class_='ayat-number-style')]
                main_ = [soup_.find_all('div', class_=f'translation-style translation-{i}', limit=len(ayat_nums)+1) for i in range(1, len(ayat_nums)+1)]
                main = [j.text.replace('\n',' ') for i in main_ for j in i]
                #** {Author: ''}
                all_authors = dict.fromkeys(['Yusuf Ali', 'Abul Ala Maududi', 'Muhsin Khan', 'Pickthall', 'Dr. Ghali', 'Abdul Haleem', 'Sahih International'], '')
                pattern = '|'.join(re.escape(k) for k in all_authors.keys())
                contents = [j.split(':', 1) for _, j in enumerate(main) if re.search(pattern, j)]
                for _, i in enumerate(contents):
                    for name_, _ in all_authors.items():
                        if i[0]==name_:
                            all_authors[name_] += f'{i[1]}\n'
                all_contents = {key: value.split('\n')[:-1] for key, value in all_authors.items()}
                enum_param = 1 if surahID==1 else 0
                for _, (name_, info) in enumerate(all_contents.items()):
                    if len(info) == len(ayat_nums):
                        data = {}
                        for idx, (id_, text, translit, cont) in enumerate(zip(ayat_nums, info, transliteration, content), start=enum_param):
                            #?> Add translations here for each verse
                            translation_ar, translit = ('', '') if name_ != 'Sahih International' else map(''.join, (cont, translit))
                            data[idx] = {
                                        'verse': id_,
                                        'translation_eng': text.lstrip(),
                                        'transliteration': translit,
                                        'translation_ar': translation_ar}
                        all_contents[name_] = data
                return all_contents
            
            surahID = response['id']
            response['surah_name_ar'] = response['surah_name_ar'][::-1]
            transliteration, content = zip(*[(j['transliteration'], j['content'][::-1]) for _, j in response['verses'].items()])
            myislam_contents = await _parse_myislam(surahID)
            
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
            response = await self._parse_surah(i, url=self.url.quran_url, headers=self.headers)
            all_contents = await _fix_surah_contents()
            surahs[response.pop('id')] = all_contents
        if export:
            return self._exporter(surahs, 'list_of_surahs')
        return surahs

    @classmethod
    def get_surah(cls, surahID: str=None):
        list_surahs, _json_file = cls._list_surahs()
        if surahID is None:
            pprint(list_surahs)
            return 'Choose a surah ID'
        else:
            return _json_file[str(surahID)]
    
    @classmethod
    def _list_surahs(cls):
        _json_file = cls._load_file(path=cls.path, name='list_of_surahs', mode='r', folder='jsons')
        modified = {int(key): unidecode(re.sub(' ', '-', value['surah_name'])) for key, value in _json_file.items()}
        sort_json = sorted(modified.items(), key=lambda i: i[0])
        surahs = OrderedDict(sort_json)
        return surahs, _json_file
    
    async def _extract_contents(self, **kwargs):
        default_values = ['']*3+['99-names-of-allah', True, self.url.myislam, None]
        html_file, class_, tag_, endpoint, slash, url, headers = tuple(kwargs.get(key, default_values[i]) for i,key in enumerate(('html_file','class_', 'tag_', 'endpoint', 'slash', 'url', 'headers')))
        main_page = await self._request(endpoint=endpoint, slash=slash, url=url, headers=headers) if not html_file else html_file
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
    
    @classmethod
    def get_instance(cls):
        return cls()

class HadithAPI(QuranAPI):
    
    async def get_all_hadiths(self, **kwargs):
        '''Fetch all hadiths or specify `author`: str'''
        async def _get_hadiths(**kwargs):
            return await _extract_urls(**kwargs)
        
        async def _extract_urls(**kwargs):
            async def _parser(contents):
                for book, link in tqdm(contents.items(), total=len(contents), desc='Processing Hadiths', colour='green', unit='MB'):
                    with open(self.path / 'jsons' / f'book_{book}.json', mode='w', encoding='utf-8') as file2:
                        hadith_json = await self._request('', slash=False, url=link)
                        json.dump(hadith_json, file2, indent=4)
                return file2
            default_values = (False, Literal[True], 'English')
            parser, _, lang = (kwargs.get(key, default_values[i]) for i,key in enumerate(('parser', 'export', 'lang')))
            json_file = await self._request('', slash=False, url=self.url.hadith_url)
            contents_ = [(nested('book', j, wild=True), nested('link', j, wild=True)) for i in json_file.values() for j in i['collection'] if j.get('language') == lang]
            contents = {key[0][0]: key[1][0] for key in contents_}
            path = Path(deepcopy(self.path))
            file = open(path / 'jsons' / 'hadith_api_links.json', mode='w', encoding='utf-8')
            json.dump(contents, file, indent=4)
            file.close()
            if parser:
                json_file = json.load(open(path / 'jsons' / 'hadith_api_links.json', encoding='utf-8'))
                await _parser(json_file)
                return contents
            else:
                return contents
        
        contents = await _get_hadiths(parser=True)
        book_authors = contents.keys()
        default_values = ['', False]
        author, _  = [kwargs.get(key, default_values[i]) for i, key in enumerate(('author', ''))]
        if author:
            author = self.best_match(author, values_=book_authors)[0]
            book_json = json.loads((self.path / 'jsons' / f'book_{author}.json').read_text(encoding='utf-8'))
            return book_json
        else:
            return contents

class IslamFacts(QuranAPI):
    facts = set()
    allah_names = dict()
    
    @classmethod
    def _update_facts(cls, facts: set):
        file2 = cls._load_file(path=cls.path, name='islam_facts', mode='r', folder='jsons', type_='json')
        fun_facts = dict.fromkeys(file2)
        fun_facts.update(facts)
        cls.facts.update(facts)
        file3 = open(cls.path / 'jsons' / 'islam_facts.json', mode='w', encoding='utf-8')
        json.dump(fun_facts, file3, indent=4, ensure_ascii=False)
        file3.close()
        return fun_facts
    
    async def fun_fact(self, **kwargs):
        def _randomizer(dict_):
            #?>Modify for more flexibily to show a random content for each method
            new_dict = tuple(dict_.keys())
            rand_fact = choice(new_dict)
            return rand_fact
        
        async def _extract_facts():
            if len(self.facts) == 0:
                #!> FunFact generator website only allows ~18 free SAME random facts
                while len(self.facts) <= 18:
                    for _ in tqdm(range(limit), leave=False, desc='Processing Fun Facts', colour='green', unit='MB'):
                        soup = await self._extract_contents(endpoint='', slash=False, 
                                                            url=self.url.islam_facts, tag_='h2')
                        fun_fact = soup[0].text
                        formatted = re.sub(r'\((Religion > Islam )\)', '', fun_fact).strip()
                        self.facts.add(formatted)
            fun_facts = dict.fromkeys(self.facts)
            with open(self.path / 'jsons' / 'islam_facts.json', mode='w', encoding='utf-8') as file1:
                json.dump(fun_facts, file1, indent=4, ensure_ascii=False)
            return fun_facts
        
        limit = kwargs.get('limit', 2)
        if not Path(self.path / 'jsons' / 'islam_facts.json').is_file():
            fun_facts = await _extract_facts()
            rand_fact = _randomizer(fun_facts)
            return rand_fact
        else:
            facts_file = json.load(open(self.path / 'jsons' / 'islam_facts.json', mode='r', encoding='utf-8'))
            self.facts = facts_file
            rand_fact = _randomizer(facts_file)
            return rand_fact
    
    async def extract_allah_contents(self, export=False):
        async def _get_name_contents():
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
                                *[extract_content(endpoint=name,   
                                                slash=True, class_=i) 
                                for i in ('name-meaning', 'summary', 
                                        'column-section', 'second-section')]
                                )
                org_names = _fixer(True)
                all_name_contents[org_names[ar_name_idx]] = _extract_name_data()
            
            del (main_page, allah_names_html)
            return all_name_contents
        
        all_contents = await _get_name_contents()
        merged_contents = {}
        for idx, (name, information) in tqdm(enumerate(all_contents.items(), start=1),
                                        total=len(all_contents), desc='Processing Names of Allah',
                                        colour='green', unit='MB'):
            merged_contents[idx] = {
                                    'Name': name,
                                    'Information': {**information}
                                    }
        del all_contents
        if export:
            return self._exporter(merged_contents, 'list_allah_names')
        return merged_contents
    
    async def islamic_terms(self, export=False):
        async def _get_soup(query):
            url = self.url.alim
            headers = None
            soup = await self._extract_contents(endpoint=f'islamic-terms-dictionary/{query}', url=url, slash=True, headers=headers)
            return soup
        
        async def _parse_letter(letter):
            letter_dictionary = {}
            letter_words = await _get_soup(letter)
            cleaned_words = ''.join([i.text for i in letter_words]).split('\n')
            all_words = [
                        OrderedDict({
                            'Term': cleaned_words[i],
                            'Definition': ' '.join([i.capitalize() for i in re.split(r'(?<=[.!?])\s+', cleaned_words[i+1])])
                        })
                        for i in range(len(cleaned_words) - 1)
                        if cleaned_words[i].startswith(letter.upper()) and cleaned_words[i + 1]
                    ]
            #** [::] Some had random content
            letter_dictionary[letter.upper()] = None if len(all_words)==0 else \
                                                all_words[7:] if letter=='T' else \
                                                all_words[2:] if letter=='R' else \
                                                all_words
            del (letter_words, all_words)
            return letter_dictionary
        
        async def _extract_all():
            queries = ascii_lowercase
            with ThreadPoolExecutor(max_workers=cpu_count()//2) as executor:
                loop = asyncio.get_event_loop()
                tasks = [await loop.run_in_executor(executor, _parse_letter, query) for query in queries]
                islamic_dictionary = await asyncio.gather(*tasks)
            return islamic_dictionary
        
        full_dictionary = await _extract_all()
        if export:
            return self._exporter(full_dictionary, 'islamic-terms')
        return full_dictionary
        

    @classmethod
    @property
    def allah_99names(cls):
        #!> Add Exception Handling if None
        return cls.allah_names
    
    @classmethod
    @property
    def get_all_facts(cls):
        return cls.facts

class PrayerAPI(QuranAPI):
    
    async def extract_qibla_data(self, export=False):
        async def _get_qibla(**kwargs):
            @lru_cache(maxsize=1)
            def _get_coords():
                Coords = namedtuple('Coords', ['lat', 'long', 'qibla'], defaults=['25.4106386', '51.1846025', None])
                loc = location(place)
                coords_qib = Coords(lat=loc.lat, long=loc.lng)
                return coords_qib
            
            place = kwargs.get('place', 'Saudia Arabia')
            coords_qib = _get_coords()
            endpoint = f'qibla/:{coords_qib.lat}/:{coords_qib.long}'
            url = self.url.aladhan
            response = await self._request(endpoint=endpoint, slash=True, url=url)
            qibla_dir = response['data'].get('direction') if response['status']=='OK' else 68.92406695044804
            coords_qib = coords_qib._replace(qibla=qibla_dir)
            return coords_qib
        
        @lru_cache(maxsize=1)
        def _extract_countries():
            pdf_contents = extract_pages(pdf_file)
            countries = ''.join([j.get_text() for i in pdf_contents for j in i])
            all_countries_ = countries.split('\n')[:-1]
            all_countries_.sort(key=lambda i: i[0])
            all_countries = dict.fromkeys(all_countries_, {})
            return all_countries
        
        pdf_file = self.path / 'pdfs' / 'all_countries.pdf'
        all_countries = _extract_countries()
        
        qibla_data = {}
        for idx, (country, _) in tqdm(enumerate(all_countries.items(), start=1), total=len(all_countries), desc='Processing Qibla Data', unit='MB', colour='green'):
            lat, long, qibla_dir = await _get_qibla(place=country)
            qibla_data[idx] = {'Country': country,
                                'latitude': lat,
                                'longitutde': long,
                                'qibla_dir': qibla_dir}
        if export:
            return self._exporter(qibla_data, 'qibla_data')
        else:
            return qibla_data

class ProphetStories(QuranAPI):
    
    async def _empty_stories(self):
        async def _get_prophets():
            main_endpoint = 'prophet-stories/'
            soup, stories_soup = await asyncio.gather(
                                self._extract_contents(endpoint=main_endpoint, slash=True,
                                                        url=self.url.myislam, class_='et_pb_text_inner'),
                                self._extract_contents(endpoint=main_endpoint, slash=True,
                                                        url=self.url.myislam)
                                )
            
            def _get_empty():
                def _fix_intros(story, prophet):
                    story = ''.join(story)
                    first_sub = re.sub(r'\d{1,3}\.\s', '', story)
                    second_sub = re.sub(rf'Story of {prophet}', '', first_sub)
                    final_sub = re.sub(r'\xa0', '', second_sub)
                    return final_sub
                
                main_stories = [i.text.split('\n') for i in soup if re.search(r'\d{1,2}\.', i.text)]
                all_prophets_ = [j.removeprefix('Story of ') for i in main_stories for j in i if re.findall(r'Story of', j)]
                all_prophets = {idx: key for idx,key in enumerate(all_prophets_, start=1)}
                prophet_intro = ''.join([i.text for i in soup if re.search(r'(Surah Nahl Ayat)', i.text)]).split('\n')[:-2]
                empty_stories = {'About Prophets': prophet_intro}
                for idx, (story, (_, prophet)) in enumerate(zip(main_stories, all_prophets.items()), start=1):
                    intro_story = _fix_intros(story, prophet)
                    empty_stories[idx] = {prophet: {'Intro': intro_story}}
                return empty_stories
            
            def _prophet_endpoints():
                pattern = re.compile(r".*Story of Prophet.*")
                links = stories_soup.find_all('p')
                prophet_endpoints = [i.a['href'].split('/')[-2] for i in links if re.search(pattern, i.get_text())]
                return prophet_endpoints
            
            return (_prophet_endpoints(), _get_empty())
        
        #** prophet_endpoints, empty_stories
        contents = await _get_prophets()
        return contents
    
    async def _extract_stories(self):
        prophets, empty_stories = await self._empty_stories()
        with ThreadPoolExecutor(max_workers=cpu_count() // 2) as executor:
            loop = asyncio.get_event_loop()
            tasks = [await loop.run_in_executor(executor, self._match_func, prophet) for prophet in prophets]
            
            with tqdm(total=len(tasks), desc="Processing Prophets", colour='green', unit='MB') as pbar:
                async def run_task(task):
                    result = await task
                    pbar.update(1)
                    return result

                completed_stories = await asyncio.gather(*[run_task(task) for task in tasks])

        return completed_stories, empty_stories
    
    async def _match_func(self, prophet):
        #** Generic methods: Propets Yunus, Yasa, Yusuf, Saleh, Sulaiman
        method_map = {
            'prophet-ayyub': self._fix_ayyub,
            'prophet-yunus': self._fix_generics,
            'story-of-prophet-lut': self._fix_lut,
            'prophet-idris': self._fix_idris,
            'prophet-dhul-kifl': self._fix_kifl,
            'prophet-nuh': self._fix_nuh,
            'prophet-al-yasa': self._fix_yasa,
            'prophet-yusuf': self._fix_generics,
            'prophet-saleh-story': self._fix_saleh,
            'story-prophet-sulaiman': self._fix_generics,
            'prophet-adam': self._fix_adam,
        }
        method = method_map.get(prophet, None)
        if method:
            return await method(prophet)
        else:
            return None
    
    @staticmethod
    def _fix_name(prophet):
        return re.findall(r'(?:story-)?(?:of-)?(?:prophet-)?(.+)', prophet)[0].title()
    
    async def _parse_html(self, prophet, soup=False, class_=None):
        response = await self._extract_contents(
                                            endpoint=prophet, slash=True,
                                            url=self.url.myislam,
                                            class_=class_)
        if not soup:
            return response
        else:
            return [i.text for i in response]
    
    async def _fix_generics(self, prophet):
        name = self._fix_name(prophet)
        dict_name = f'Prophet {name}'
        all_contents = dict.fromkeys([dict_name], {})
        soup = await self._parse_html(prophet, soup=True)
        clean_contents_ = ' '.join(soup).split('\n')
        clean_contents = [i.replace('\xa0','') for i in clean_contents_ if i and not re.search(r'Prophet Stories', i)]
        pattern = re.compile(r'The Story (?:Of\s)?Prophet (\w+)(?: \((PBUH)\))?', re.IGNORECASE)
        first_key = pattern.search(''.join(clean_contents)).group()
        first_index = clean_contents.index(first_key)
        end_index = clean_contents.index('Support the site?')
        all_contents[dict_name] = {first_key: clean_contents[first_index:end_index-2][1:]}
        return all_contents
    
    async def _fix_ayyub(self, prophet):
        name = self._fix_name(prophet)
        dict_name = f'Prophet {name}'
        all_contents = dict.fromkeys([dict_name], {})
        soup = await self._parse_html(prophet, soup=False, class_='et_pb_section et_pb_section_1 et_section_regular')
        fam_tree_key = [i.div.strong.get_text() for i in soup][0]
        html_contents = [i.text for i in soup]
        cleaned_contents = [i.replace('\xa0', '') for i in ' '.join(html_contents).split('\n') if i and not re.search(rf'{fam_tree_key}|Back To Prophet Stories', i)]
        verse_mentions_key, verse_section = re.findall(rf'Quranic Verses Mentioning\s\w+', ''.join(html_contents))[0], cleaned_contents.index('Quranic Verses Mentioning Ayyub')
        fam_tree_contents, verse_contents = cleaned_contents[:verse_section], cleaned_contents[verse_section+1:]
        all_contents[dict_name] = {
                            fam_tree_key: fam_tree_contents,
                            verse_mentions_key: verse_contents}
        return all_contents
    
    async def _fix_lut(self, prophet):
        name = self._fix_name(prophet)
        dict_name = f'Prophet {name}'
        all_contents = dict.fromkeys([dict_name], {})
        soup = await self._parse_html(prophet, soup=False)
        html_contents = [i.text for i in soup]
        clean_contents_ = ' '.join(html_contents).split('\n')
        clean_contents = [i.replace('\xa0', '') for i in clean_contents_ if i and not re.search(r'Return To Prophet Stories', i)]
        first_key = 'The Story Of Prophet Lut in Islam'
        first_index = clean_contents.index(first_key)
        second_section_key = 'Quran Verses That Mention The Story Of Prophet Lut'
        second_index = clean_contents.index(second_section_key)
        end_index = clean_contents.index('Support the site?')
        first_section_contents, second_section_contents = clean_contents[first_index:second_index][1:], clean_contents[second_index+1:end_index-2]
        all_contents[dict_name] = {
                            first_key: first_section_contents,
                            second_section_key: second_section_contents
                            }
        
        return all_contents
    
    async def _fix_idris(self, prophet):
        name = self._fix_name(prophet)
        dict_name = f'Prophet {name}'
        all_contents = dict.fromkeys([dict_name], {})
        soup = await self._parse_html(prophet, soup=True)
        clean_contents_ = ' '.join(soup).split('\n')
        clean_contents = [i.replace('\xa0', '') for i in clean_contents_ if i and not re.search(r'List Of Prophets In Islam', i)]
        first_key = 'Story of Prophet Idris In Islam'
        first_index = clean_contents.index(first_key)
        second_key = 'Prophet Idris Story'
        second_index = clean_contents.index(second_key)
        end_index = clean_contents.index('Support the site?')
        first_contents, second_contents = clean_contents[first_index:second_index][1:], clean_contents[second_index+1:end_index-2]
        all_contents[dict_name] = {
                        first_key: first_contents,
                        second_key: second_contents
        }
        return all_contents
    
    async def _fix_kifl(self, prophet):
        name = self._fix_name(prophet)
        dict_name = f'Prophet {name}'
        all_contents = dict.fromkeys([dict_name], {})
        soup = await self._parse_html(prophet, soup=True)
        clean_contents_ = ' '.join(soup).split('\n')
        clean_contents = [i.replace('\xa0','') for i in clean_contents_ if i and not re.search(r'List Of Prophets In Islam', i) and not i==' ']
        first_key = 'Prophet Dhul Kifl'
        first_index = clean_contents.index('Prophet Dhul Kifl')
        second_key = 'Story Of Prophet Dhul-Kifl by Ibn jarir'
        second_index = clean_contents.index(second_key)
        end_index = clean_contents.index('Support the site?')
        first_contents, second_contents = clean_contents[first_index:second_index][2:], clean_contents[second_index+1:end_index-1]
        all_contents[dict_name] = {
                        first_key: first_contents,
                        second_key: second_contents
        }
        return all_contents
    
    async def _fix_nuh(self, prophet):
        name = self._fix_name(prophet)
        dict_name = f'Prophet {name}'
        all_contents = dict.fromkeys([dict_name], {})
        soup = await self._parse_html(prophet, soup=True)
        clean_contents_ = ' '.join(soup).split('\n')
        clean_contents = [i.replace('\xa0','') for i in clean_contents_ if i and not re.search(r'Prophet Stories', i)]
        first_key = re.search(rf'Prophet {name}', ''.join(clean_contents)).group()
        first_index = clean_contents.index(first_key)
        second_key = 'References that refer to Prophet Noah'
        second_index = clean_contents.index('Imran (3:33)')
        end_index = clean_contents.index('Support the site?')
        first_contents, second_contents = clean_contents[first_index:second_index-1][1:-1], clean_contents[second_index-1:end_index-2]
        all_contents[dict_name] = {
                    first_key: first_contents,
                    second_key: second_contents
        }
        return all_contents
    
    async def _fix_adam(self, prophet):
        name = self._fix_name(prophet)
        dict_name = f'Prophet {name}'
        all_contents = dict.fromkeys([dict_name], {})
        soup = await self._parse_html(prophet, soup=True, class_='et_pb_module et_pb_code et_pb_code_0')
        clean_contents_ = ''.join(soup).split('\n')
        clean_contents = [i.replace('\xa0','') for i in clean_contents_ if i]
        first_key = 'STORY OF PROPHET ADAM (AS) IN ISLAM'.title()
        second_key = 'Adam (PBUH) learns the names of everything:'
        second_index = clean_contents.index(second_key)
        first_contents, second_contents = clean_contents[:second_index], clean_contents[second_index+1:]
        all_contents[dict_name] = {
                    first_key: first_contents,
                    second_key.strip(':'): second_contents
        }
        return all_contents
    
    async def _fix_yasa(self, prophet):
        name = self._fix_name(prophet)
        dict_name = f'Prophet {name}'
        all_contents = dict.fromkeys([dict_name], {})
        soup = await self._parse_html(prophet, soup=True)
        clean_contents_ = ' '.join(soup).split('\n')
        clean_contents = [i.replace('\xa0','') for i in clean_contents_ if i and not re.search(r'Prophet Stories', i)]
        first_key = re.search(r'Story of Al-Yasa \(Elisha\)', ''.join(clean_contents)).group()
        first_index = clean_contents.index(first_key)
        end_index = clean_contents.index('Support the site?')
        all_contents[dict_name] = {first_key: clean_contents[first_index:end_index-2]}
        return all_contents
    
    async def _fix_saleh(self, prophet):
        name = self._fix_name(prophet)
        dict_name = f'Prophet {name.rstrip("-Story")}'
        all_contents = dict.fromkeys([dict_name], {})
        soup = await self._parse_html(prophet, soup=True)
        clean_contents_ = ' '.join(soup).split('\n')
        clean_contents = [i.replace('\xa0','') for i in clean_contents_ if i and not re.search(r'Prophet Stories', i)]
        pattern = re.compile(r'Story (?:Of\s)?Prophet (\w+)', re.IGNORECASE)
        first_key = pattern.search(''.join(clean_contents)).group()
        first_index = clean_contents.index(first_key)
        end_index = clean_contents.index('Support the site?')
        all_contents[dict_name] = {first_key: clean_contents[first_index:end_index-2][1:]}
        return all_contents
    
    async def extract_all_prophets(self, export=False):
        completed_stories, empty_stories = await self._extract_stories()
        all_contents = {idx: {j: {'Full Story': k, 'Intro': empty_stories[idx].get(j)['Intro']}} 
                            for idx, name in enumerate(completed_stories, start=1) 
                            for j, k in name.items()}

        if export:
            with open(self.path / 'jsons' / 'prophet_stories.json', mode='w', encoding='utf-8') as file:
                json.dump(all_contents, file, indent=4, ensure_ascii=False)
            return all_contents
        return all_contents

class ProphetMuhammad(QuranAPI):
    def __init__(self):
        self.name = 'The Life of the Prophet Muhammad (Peace and blessings of Allah be upon him)'
        self.title = 'The-Life-of-The-Prophet-Muhammad'
    
    async def _pdf_parser(self):
        def _cleaner(contents):
        #** Removes page numbers and header: 'The Life of the Prophet Muhammad (Peace and blessings of Allah be upon him)'
            header_pattern = re.escape(self.name)
            pattern = fr'\d{{1,2}}|{header_pattern}'
            fixed_contents = [re.sub(pattern, '', i) if re.match(pattern, i) else i for i in contents]
            cleaned_contents_ = ' '.join([i.strip() for i in fixed_contents if i]).strip()
            cleaned_contents = '{}{}'.format(cleaned_contents_, '.' if not cleaned_contents_.endswith('.') else '')
            return cleaned_contents
        
        async def _title_page():
            def _get_toc():
                #** Table of Contents
                toc_page = self._extractor(pdf, page_numbers=[3])
                toc_contents = [i.split('.', 1)[0].rstrip() for i in toc_page[3:-1]]
                updated_toc = {idx: content for idx, content in enumerate(toc_contents, start=1)}
                return updated_toc
            
            title_page = self._extractor(pdf, maxpages=2)
            title_contents = list(map(lambda i: i.strip(), title_page))[:-8]
            title = ' '.join([title_contents.pop(0) for _ in range(3)])
            translation_ar, translation_en = [title_contents.pop(0) for _ in range(2)]
            toc_contents = _get_toc()
            updated_title = {title: {
                                    'introduction': ''.join(title_contents),
                                    'transliteration_ar': translation_ar,
                                    'transliteration_en': translation_en,
                                    'table_of_contents': {**toc_contents}
                                    }}
            del title_page
            return updated_title
        
        async def _parse_chap(start_page, end_page):
            chap_page = self._extractor(pdf, page_numbers=range(start_page, end_page + 1))[3:]
            chap_contents = _cleaner(chap_page)
            return chap_contents
        
        async def _parse_gloss():
            def _clean_gloss():
                glossary_page = self._extractor(pdf, page_numbers=range(85, 91))[3:]
                header_pattern = re.escape(self.name)
                pattern = fr'{header_pattern}'
                glossary_contents = [i.strip() for i in glossary_page if not re.match(pattern, i)]
                cleaned_contents = [i for i in glossary_contents if i and not re.match(r'\d{2}', i)]
                return cleaned_contents
            
            gloss_contents = _clean_gloss()
            abd_allah = gloss_contents[0], ' '.join(gloss_contents[1:3])
            abd_ibn_1 = gloss_contents[3].split('   ')[0]+'-1', gloss_contents[3].split('   ')[1]
            ubayy = gloss_contents[4], ' '.join(gloss_contents[5:8])
            abd_al = gloss_contents[8], gloss_contents[9]
            muttalib = gloss_contents[10], ' '.join(gloss_contents[11:13])
            abd_ibn_2 = gloss_contents[13].split('   ')[0]+'-2', gloss_contents[13].split('   ')[1]
            abu_rabiah = gloss_contents[14].split('   ')[0], gloss_contents[14].split('   ')[1]
            abdu_manaf = gloss_contents[15].split('   ')[0], gloss_contents[15].split('   ')[1]+gloss_contents[16]
            abrahah = gloss_contents[17], ' '.join(gloss_contents[18:20])
            abraham_ib = ' '.join(gloss_contents[20:22]), ' '.join(gloss_contents[22:29])
            abo_bakr = gloss_contents[29], ' '.join(gloss_contents[30:34])
            abu_dujanah = gloss_contents[34].split('   ')[0], gloss_contents[34].split('   ')[1]+ ' '.join(gloss_contents[35:37])
            abujahl = gloss_contents[37], ' '.join(gloss_contents[39:46])
            abu_sufyan = gloss_contents[38], ' '.join(gloss_contents[46:50])
            abo_talib = gloss_contents[50], ' '.join(gloss_contents[51:55])
            addas = gloss_contents[55], ' '.join(gloss_contents[56:60])
            adhan = gloss_contents[60], gloss_contents[61]
            aisah = gloss_contents[62], ' '.join(gloss_contents[63:65])
            al_abbas = gloss_contents[65], ' '.join(gloss_contents[66: 69])
            ali = gloss_contents[69], ' '.join(gloss_contents[70:73])
            allahu_akar = gloss_contents[73].split('   ')[0], gloss_contents[73].split('   ')[1]
            alms = gloss_contents[74], gloss_contents[75]
            aminah = gloss_contents[76], gloss_contents[77]
            amro_ibun_ = gloss_contents[78].split('   ')
            amro_ibun = f'{amro_ibun_[0]} {amro_ibun_[1]}', ' '.join(amro_ibun_[2:])
            al_ass = gloss_contents[79], ' '.join(gloss_contents[81:84])
            ansar = gloss_contents[80], '{} {} {}'.format(' '.join(gloss_contents[84:86]), gloss_contents[87], gloss_contents[86])
            apostle = gloss_contents[88], gloss_contents[89]
            
            #!> FINISH GLOSSARY
            updated_gloss = OrderedDict({
                            abd_allah[0]: abd_allah[1],
                            abd_ibn_1[0]: abd_ibn_1[1],
                            ubayy[0]: ubayy[1],
                            abd_al[0]: abd_al[1],
                            muttalib[0]: muttalib[1],
                            abd_ibn_2[0]: abd_ibn_2[1],
                            abu_rabiah[0]: abu_rabiah[1],
                            abdu_manaf[0]: abdu_manaf[1],
                            abrahah[0]: abrahah[1],
                            abraham_ib[0]: abraham_ib[1],
                            abo_bakr[0]: abo_bakr[1],
                            abu_dujanah[0]: abu_dujanah[1],
                            abujahl[0]: abujahl[1],
                            abu_sufyan[0]: abu_sufyan[1],
                            abo_talib[0]: abo_talib[1],
                            addas[0]: addas[1],
                            adhan[0]: adhan[1],
                            aisah[0]: aisah[1],
                            al_abbas[0]: al_abbas[1],
                            ali[0]: ali[1],
                            allahu_akar[0]: allahu_akar[1],
                            alms[0]: alms[1],
                            aminah[0]: aminah[1],
                            amro_ibun[0]: amro_ibun[1],
                            al_ass[0]: al_ass[1],
                            ansar[0]: ansar[1],
                            apostle[0]: apostle[1]
                            })
            del gloss_contents
            return updated_gloss
        
        pdf = self._get_file(path=self.path, file_name=self.title)
        title_page, glossary = await asyncio.gather(
                                    _title_page(),
                                    _parse_gloss()
                                    )
        
        chapters = {
                    1: (4, 8),    2: (8, 10),   3: (10, 11), 
                    4: (12, 13),  5: (14, 15),  6: (16, 17),
                    7: (18, 19),  8: (20, 22),  9: (23, 24),
                    10: (25, 27), 11: (28, 29), 12: (30, 32),
                    13: (33, 35), 14: (36, 37), 15: (38, 39),
                    16: (40, 41), 17: (42, 44), 18: (45, 46),
                    19: (47, 50), 20: (51, 54), 21: (55, 59),
                    22: (60, 63), 23: (64, 68), 24: (69, 72),
                    25: (73, 75), 26: (76, 78), 27: (79, 82),
                    28: (83, 84)
                }
        
        with ThreadPoolExecutor(max_workers=cpu_count() // 2) as executor:
            loop = asyncio.get_event_loop()
            tasks = [await loop.run_in_executor(executor, _parse_chap, *chap) for chap in chapters.values()]
            chapters = await asyncio.gather(*tasks)
        chapters = {idx: contents for (idx, contents) in enumerate(chapters, start=1)}
        return (title_page, chapters, glossary)
    
    async def proph_muhammads_life(self, export=False):
        title_page, chapters, glossary = await self._pdf_parser()
        toc_contents = nested('table_of_contents', title_page)[0]
        toc_and_chaps = {idx: {chap: chapters.get(idx) if idx!=29 else glossary}
                            for idx, chap in tqdm(enumerate(toc_contents.values(), start=1),
                                                total=len(toc_contents.values()),
                                                desc='Processing Life-of-Prophet-Muhammad PDF',
                                                unit='MB',
                                                colour='green')}
        title_page[self.name]['table_of_contents'] = toc_and_chaps
        full_book = deepcopy(title_page)
        
        del (title_page, chapters, glossary)
        
        if export:
            return self._exporter(full_book, 'life_of_prophet_muhammad')
        return full_book

class IslamicStudies(QuranAPI):
    
    async def islamic_timeline(self, export=False):
        async def _get_timeline():
            timeline_data = [i.text for i in soup.find_all('p')]
            centuries = [(idx, i) for idx, i in enumerate(timeline_data) if re.search(r'\d{1,2}(?:th) Century', i)]
            return (centuries, timeline_data)
        
        def _get_contents(contents, start, end):
            contents = contents[start+1:end]
            updated_contents = [i.replace('\n','').strip() for i in contents][:-1]
            return updated_contents
        
        async def _get_credits():
            return soup.find('h3').text
            
        async def _parse_timeline():
            time_data, credentials = await asyncio.gather(
                                                    _get_timeline(),
                                                    _get_credits()
                                                    )
            centuries, timeline_data = time_data
            grouped_cent = [(centuries[i], centuries[i + 1]) for i in range(0, len(centuries)-1, 1)]
            all_contents = OrderedDict()
            for _, idx_century in tqdm(enumerate(grouped_cent), total=len(grouped_cent), desc='Processing Islamic Timeline', colour='green', unit='MB'):
                key = idx_century[0][1].replace('\n', '').strip()
                indexes = (idx_century[0][0], idx_century[1][0])
                all_contents[key] = _get_contents(timeline_data, indexes[0], indexes[1])
            all_contents['Credits'] = credentials
            
            if export:
                return self._exporter(all_contents, 'islamic_timeline')
            return all_contents
        
        html_file = open(self.path / 'htmls' / 'Timeline (History of Islam).html', mode='r', encoding='utf-8').read()
        soup = BeautifulSoup(html_file, 'html.parser')
        return await _parse_timeline()
    
    async def get_islam_laws(self, export=False):
        
        @lru_cache(maxsize=1)
        async def _get_docx():
            return Document(self.path / 'docxs' / 'islam-laws.docx')
        
        def _table_extractor(table_index=0, columns=False):
            if table_index < len(docx.tables):
                table = docx.tables[table_index]
                table_data = []
                
                for row in table.rows:
                    row_data = []
                    for cell in row.cells:
                        cell_text = ''
                        for paragraph in cell.paragraphs:
                            cell_text += paragraph.text.strip() + '\n'
                        row_data.append(cell_text.strip())
                    table_data.append(row_data)
                if columns:
                    return _table_extractor()[0]
                return table_data
            else:
                return None
        
        def _content_extractor():
            all_contents = {}
            for i in tqdm(range(2), desc='Processing Islamic Laws', unit='MB', colour='green'):
                for j in _table_extractor(i)[1:]:
                    j = list(map(lambda i: i.replace('\n',''), j))
                    all_contents[f'Category-({j[0]})'] = {
                                            'Prohibited (Haram)': j[1],
                                            'Lawful (Halal)': j[2],
                                            'Comments': j[3]
                                            }
            all_contents = {idx: content for idx, content in enumerate(all_contents.items(), start=1)}
            return all_contents
        
        docx = await _get_docx()
        structured_contents = _content_extractor()
        del docx
        
        if export:
            return self._exporter(structured_contents, 'islamic-laws')
        return structured_contents
    
    async def road_peace_html(self, export=False):
        
        @lru_cache(maxsize=1)
        async def _get_html():
            html_file = open(self.path / 'htmls' / 'The Road to Peace and Salvation.html', mode='r', encoding='utf-8')
            soup = await self._extract_contents(html_file=html_file)
            return soup
        
        def _get_contents(*args):
            contents, start, end = args
            contents = ''.join(contents[start+1:end]).strip()
            return contents
        
        async def _cleaned_html():
            html = await _get_html()
            html_contents = ''.join([i.text for i in [i for i in html if i]]).split('\n')
            old_html_ = [i for i in html_contents if not re.match(r'(?:\d{1,2})\/16The Road to Peace and Salvation', i)]
            old_html = [i for i in old_html_[1:] if i]
            credentials = html.find('h3').text
            title = ' '.join([old_html.pop(1) for _ in range(3)])
            _ = [old_html.pop(idx) for idx, i in enumerate(old_html) if re.match(r'Chapter (?:\d{1}) ', i)]
            toc_contents = [i[i.find('. ')+2:i.find(' -')] for i in html_contents if re.search(r'(?:\d{1}\.)\s(?:\w+)', i)][:-1]
            intro_ = old_html[old_html.index('INTRODUCTION')+1:old_html.index('ON THE EXISTENCE OF THE DIVINE BEING')]
            intro = ''.join(intro_).strip('Chapter 1 ')
            cleaned_html_ = [re.sub(r'(Chapter (?:\d{1}) )|(?:\d{1,2})\/16', '', i) if re.search(r'(Chapter (?:\d{1}) )|(?:\d{1,2})\/16', i) else i for i in old_html]
            cleaned_toc = {title: 
                        {'Intro': intro,
                        'table_of_contents':
                        {idx: index_name for idx, index_name in enumerate(toc_contents, start=1)},
                        'Credits': credentials}}
            cleaned_html = [i for i in cleaned_html_ if i][8:] #** Excluding toc contents
            del (html, html_contents)
            return (cleaned_toc, cleaned_html)
        
        async def _structured_contents():
            toc_contents, html = await _cleaned_html()
            title = list(toc_contents.keys())[0]
            
            def _get_toc():
                toc_indexes = [(idx, i) for idx, i in enumerate(html) if i.isupper()]
                toc_grouped = [(toc_indexes[i], toc_indexes[i + 1]) for i in range(0, len(toc_indexes) - 1)]
                return toc_grouped
            
            def _updated_toc():
                toc_indexes = _get_toc()
                updated_toc = {}
                last_idx = []
                for idx, content in tqdm(enumerate(toc_indexes), total=5,
                                        desc='Processing Road-to-Peace-and-Salvation HTML',
                                        colour='green', unit='MB'):
                    if idx==0:
                        #** Intro content already implemented
                        continue
                    key = content[0][1].title()
                    indexes = (content[0][0], content[1][0])
                    contents = _get_contents(html, *indexes)
                    updated_toc[idx] = {key: contents}
                    last_indexes = (content[1][0], content[1][1])
                    last_idx.append(last_indexes)
                    if idx==4:
                        key = last_idx[-1][1].title().strip()
                        indexes = (last_idx[-1][0], len(html))
                        contents = _get_contents(html, *indexes)
                        updated_toc[5] = {key: contents}
                del (toc_indexes, last_idx)
                return updated_toc
            
            all_contents = OrderedDict({
                                    title: {
                                        'Intro': toc_contents[title]['Intro'],
                                        'table_of_contents': _updated_toc(),
                                        'Credits': toc_contents[title]['Credits']
                                            }
                                        })
            del (toc_contents, html, title)
            
            if export:
                with open(self.path / 'jsons' / 'road_to_peace_salvation.json', mode='w', encoding='utf-8') as file:
                    json.dump(all_contents, file, indent=4, ensure_ascii=False)
                return all_contents
            return all_contents
        
        return await _structured_contents()

class IslamPrayer(QuranAPI):
    
    @staticmethod
    def _get_indexes(page, pattern=None, found=False):
        if pattern:
            norm_indexes = [(idx, i) for idx,i in enumerate(page) if re.search(pattern, i)]
            grouped_index = [(norm_indexes[i], norm_indexes[i + 1]) for i in range(0, len(norm_indexes)-1)]
        if found:
            '''Mainly for wudu-foundations'''
            norm_indexes = [(idx, i) for idx,i in enumerate(page) if i.isupper()]
            grouped_index = [(norm_indexes[i], norm_indexes[i + 1]) for i in range(0, len(norm_indexes)-1)]
        norm_indexes.append(((norm_indexes[-1]), (len(page),norm_indexes[-1][-1])))
        grouped_index.append(((grouped_index[-1][-1]), (len(page),grouped_index[-1][-1][-1])))
        return grouped_index, norm_indexes
    
    async def get_wudu(self, export=False):
        def _cleaner(page_contents):
            return [i for i in page_contents if re.search(r'\w+', i) and not re.match(r'(?:\d{1,2})|(?:How to Perform Wudu\’ \(Step-by-Step\))', i)]
        
        async def _wudu_foundations():
            page = self._get_page(wudu_guide, 10, 11)[:-1]
            title_contents = page.pop(0)
            indexes = self._get_indexes(page, found=True)[0]
            foundation = {title_contents: {}}
            for idx, (i,j) in enumerate(indexes, start=1):
                start, end = i[0], j[0] if j[0] != len(page) else len(page)
                key = i[1].title()
                contents = _get_contents(page, start, end)
                foundation[title_contents][idx] = {key: list(contents.split('  '))}
                if idx==3:
                    structured_dict = {}
                    current_key = None
                    contents = list(contents.split()[:-1])[:-2]
                    for item in contents:
                        if re.match(r'(?:\d{1})\.', item):
                            current_key = item.strip('.')
                            structured_dict[current_key] = ''
                        elif current_key is not None:
                            structured_dict[current_key] += f' {item}'
                    foundation[title_contents][idx] = {key: structured_dict}
            return foundation
        
        async def _title_contents():
            page_ = self._get_page(wudu_guide, 11, 12)
            page = _cleaner(page_)
            wudu_title_contents = [page.pop(0).rstrip() for _ in range(3)][::2]
            return wudu_title_contents
        
        def _get_contents(*args):
            contents, start, end = args
            old_contents = ' '.join(contents[start+1:end]).rstrip()
            return old_contents
        
        def _format_page(page, g_index):
            '''g_index: grouped_indexes'''
            steps = {}
            for i, j in g_index:
                start, end = i[0], j[0] if j[0] != len(page) else len(page)
                step_name = i[1]
                contents = _get_contents(page, start, end)
                steps[step_name] = contents
            return steps
        
        async def _wudu_contents():
            pages_ = [self._get_page(wudu_guide, *i) for _,i in enumerate(((11,14), (14, 15)))]
            pages = [_cleaner(i) for i in pages_]
            first_six, nine_ten = pages
            step_sev = first_six.index('Step 7 - Head')
            
            def _sev_eight():
                sev = first_six[step_sev:len(first_six)]
                sev_key, eight_key = [sev.pop(0) for _ in range(2)]
                sev_cont, eight_cont = sev[:4], sev[4:]
                sev_eight = {
                            sev_key: sev_cont,
                            eight_key: eight_cont
                            }
                updated_both = {idx: {key:value} for idx, (key,value) in enumerate(sev_eight.items(), start=7)}
                return updated_both
            
            def _fix_ten():
                label = 'Step 10 - Closing Du’a/Invocation'
                ten = both_fixed[-1].get(label)
                ten_idx = ten.find(label)
                ten_cont = ten[ten_idx+len(label)+1:]
                both_fixed[-1][label] = ten_cont
                both_fixed[-1] = {idx: {key:list(value.split('  '))} for idx,(key,value) in enumerate(both_fixed[-1].items(), start=9)}
                return both_fixed[-1]
            
            updated_six = first_six[3:step_sev]
            merged_pages = updated_six + nine_ten
            sev_eight = _sev_eight()
            both_indexes = [self._get_indexes(i, r'Step \d{1,2}')[0] for _,i in enumerate((updated_six, nine_ten))]
            both_fixed = [_format_page(merged_pages, i) for i in both_indexes]
            both_fixed[-1] = _fix_ten()
            both_fixed[0] = {idx: {key: list(value.split('  '))} for idx,(key,value) in enumerate(both_fixed[0].items(), start=1)}
            both_fixed[0].update(sev_eight)
            both_fixed[0].update(both_fixed[-1])
            wudu_contents = OrderedDict(both_fixed[0])
            return wudu_contents
        
        wudu_guide = self._get_file(path=self.path, file_name='salah-guide')
        title_contents, wudu_contents, foundation = await asyncio.gather(
                                                                _title_contents(),
                                                                _wudu_contents(),
                                                                _wudu_foundations()
                                                                )
        
        def merge_all():
            title, desc = title_contents
            all_merged = {
                'Wudu-Guide': {
                            'Introduction': {**foundation},
                            title: {desc: {**wudu_contents}}
                            }
                        }
            return all_merged
        
        all_contents = merge_all()
        if export:
            return self._exporter(all_contents, 'wudu-guide')
        return all_contents


    
async def main():
    # tracemalloc.start()

    # a = QuranAPI()
    # b = HadithAPI()
    # c = IslamFacts()
    # d = PrayerAPI()
    # e = ProphetStories()
    # f = ProphetMuhammad()
    # g = IslamicStudies()
    h = IslamPrayer()
    
    async def run_all(default):
        tasks = [asyncio.create_task(task) for task in [
                    # d.extract_qibla_data(default),
                    # a.extract_surahs(default),
                    # a.get_stats(export=default),
                    # b.get_all_hadiths(parser=default),
                    # c.extract_allah_contents(default),
                    # c.fun_fact(limit=18),
                    # e.extract_all_prophets(False),
                    # f.proph_muhammads_life(False),
                    # g.islamic_timeline(default),
                    # g.get_islam_laws(default),
                    # g.road_peace_html(False),
                    # c.islamic_terms(default),
                    h.get_wudu(True)
                    ]]
        results = await asyncio.gather(*tasks)
        return results
    
    start = time()
    # try:
    #     results = await run_all()
    #     # pprint(results)
    # except Exception as e:
    #     traceback = tracemalloc.get_object_traceback(e)
    #     print(traceback)
    results = await run_all(True)
    end = time()
    pprint(results)
    timer = (end-start)
    minutes, seconds = divmod(timer, 60) 
    print(f"Execution Time: {minutes:.0f} minutes and {seconds:.5f} seconds")

if __name__ == '__main__':
    asyncio.run(main())
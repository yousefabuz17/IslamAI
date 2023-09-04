import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
import asyncio
from asyncio import to_thread
import json
import re
import threading
from collections import OrderedDict, namedtuple
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
# import tensorflow as tf
from aiohttp import (ClientSession, TCPConnector, client_exceptions)
from ascii_graph import Pyasciigraph
from bs4 import BeautifulSoup
from nested_lookup import nested_lookup as nested
from rapidfuzz import (fuzz, process)
from tqdm import tqdm
# from transformers import MarianConfig, MarianMTModel, MarianTokenizer, pipeline
# import gensim
# from gensim.models import Word2Vec
# from nltk.tokenize import word_tokenize
from unidecode import unidecode
from geocoder import location
from pdfminer.high_level import extract_pages
from multiprocessing import cpu_count
from concurrent.futures import ThreadPoolExecutor


class ConfigInfo:
    _config = None
    
    def __init__(self, key):
        config = self._get_config(key)
        for key, value in config.items():
            setattr(self, key, value)

    @classmethod
    @lru_cache(maxsize=None)
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

class Translate:
    
    # @classmethod
    # @lru_cache(maxsize=1)
    # def _translate_text(cls, *args):
    #     text, src_lang, tgt_lang = args
    #     model_name = f'Helsinki-NLP/opus-mt-{src_lang}-{tgt_lang}'
    #     config = MarianConfig.from_pretrained(model_name, revision="main")
    #     model = MarianMTModel.from_pretrained(model_name, config=config)
    #     tokenizer = MarianTokenizer.from_pretrained(model_name, config=config)
    #     translation = pipeline("translation", model=model, tokenizer=tokenizer)
    #     translated_text = translation(text, max_length=512, return_text=True)[0]
    #     return translated_text.get('translation_text')

    # def translate(self, *args):
    #     return self._translate_text(*args)

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
    config: None=ConfigInfo('Database')
    path: None=Path(__file__).parent.absolute() / 'islamic_data'

class QuranAPI(BaseAPI, metaclass=SingletonMeta):
    def __init__(self):
        self.url = self.config
        self.headers = {
            "X-RapidAPI-Key": self.config.quran_api,
            "X-RapidAPI-Host": self.config.quran_host
        }
    
    async def _request(self, endpoint: Union[int, str], **kwargs):
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
        except (client_exceptions.ServerDisconnectedError) as e:
            raise e
    
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
            print('Modify \'Pyasciigraph\' module!\n Change all \'collections.Iterable\' -> \'collections.abc.Iterable\'')
    
    async def extract_surahs(self, export=False):
        async def _fix_surah_contents():
            async def _parse_myislam(surah_id):
                soup = await self._extract_contents(endpoint='quran-transliteration', slash=True, url=self.url.myislam, headers=None)
                parsed_links = [re.search(r'<a\s+href="([^"]+)">', str(i)).group() for i in soup.find_all('a') if re.search(r'<a\s+href="([^"]+)">', str(i))]
                main_endpoints = [i[:-3].split('/')[-1] for i in parsed_links if re.findall(r'at|surah\-\w+\-?\w+?', i)][2:-2]
                all_endpoints = {idx: key for idx,key in enumerate(main_endpoints, start=1)}
                surah_endpoint = all_endpoints.get(surah_id)
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
                enum_param = 1 if surah_id==1 else 0
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
            
            surah_id = response['id']
            response['surah_name_ar'] = response['surah_name_ar'][::-1]
            transliteration, content = zip(*[(j['transliteration'], j['content'][::-1]) for _, j in response['verses'].items()])
            myislam_contents = await _parse_myislam(surah_id)
            
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
        for i in tqdm(range(1, 115), desc='Processing Surahs', colour='green', unit='MB', leave=False):
            response = await self._parse_surah(i)
            all_contents = await _fix_surah_contents()
            surahs[response.pop('id')] = all_contents
        if export:
            with open(self.path / 'jsons' / 'list_of_surahs.json', mode='w', encoding='utf-8') as file:
                json.dump(surahs, file, indent=4)
        return surahs

    @classmethod
    def get_surah(cls, surah_id: str=None):
        list_surahs, _json_file = cls._list_surahs()
        if surah_id is None:
            pprint(list_surahs)
            return 'Choose a surah ID'
        else:
            return _json_file[str(surah_id)]
    
    @classmethod
    def _list_surahs(cls):
        _json_file = cls._load_file(path=cls.path, name='list_of_surahs', mode='r', folder='jsons')
        modified = {int(key): unidecode(re.sub(' ', '-', value['surah_name'])) for key, value in _json_file.items()}
        sort_json = sorted(modified.items(), key=lambda i: i[0])
        surahs = OrderedDict(sort_json)
        return surahs, _json_file
    
    async def _extract_contents(self, **kwargs):
        default_values = ['']*2+['99-names-of-allah', True, self.url.myislam, None]
        class_, tag_, endpoint, slash, url, headers = tuple(kwargs.get(key, default_values[i]) for i,key in enumerate(('class_', 'tag_', 'endpoint', 'slash', 'url', 'headers')))
        main_page = await self._request(endpoint=endpoint, slash=slash, url=url, headers=headers)
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
    
    # def _export(**kwargs):
    #     default_values = (Path(__file__).parent.absolute(), 'list_allah_names.json', 'w', 'utf-8')
    #     export = kwargs.get('export', True)
    #     if export:
    #         with open(self.path / 'list_allah_names.json', mode='w', encoding='utf-8') as file:
    #             json.dump(merged_contents, file, indent=4)
    
    #!>Merge these methods
    
    @lru_cache(maxsize=1)
    @staticmethod
    def _load_file(path, name, mode='r', encoding='utf-8', type_='json', folder='jsons'):
        #!> Modify for flexibility
        return json.load(open(path / folder / f'{name}.{type_}', mode=mode, encoding=encoding))
    
    @classmethod
    def get_instance(cls):
        return cls()

class HadithAPI(QuranAPI):
    def __init__(self):
        super().__init__()

    async def _extract_urls(self, **kwargs):
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
        
    async def _get_hadiths(self, **kwargs):
        return await self._extract_urls(**kwargs)
    
    async def get_hadith(self, **kwargs):
        contents = await self._get_hadiths(parser=True)
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
    
    def __init__(self):
        super().__init__()
    
    @classmethod
    def _update_facts(cls, facts: set):
        file2 = cls._load_file(path=cls.path, name='islam_facts', mode='r', folder='jsons')
        fun_facts = dict.fromkeys(file2)
        fun_facts.update(facts)
        cls.facts.update(facts)
        file3 = open(cls.path / 'jsons' / 'islam_facts.json', mode='w', encoding='utf-8')
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
        if not Path(self.path / 'jsons' / 'islamic_facts.json').is_file():
            if len(self.facts) == 0:
                #!> FunFact generator website only allows ~18 free SAME random facts
                while len(self.facts) <= 18:
                    for _ in tqdm(range(limit), leave=False, desc='Processing Fun Facts', colour='green', unit='MB'):
                        soup = await self._extract_contents(endpoint='', slash=False, 
                                                            url=self.url.islam_facts, tag_='h2')
                        fun_fact = soup[0].text
                        formatted = re.sub(r'\((Religion > Islam )\)', '', fun_fact).strip()
                        self.facts.add(formatted)
            # print('All fun facts parsed and saved')
            fun_facts = dict.fromkeys(self.facts)
            with open(self.path / 'jsons' / 'islam_facts.json', mode='w', encoding='utf-8') as file1:
                json.dump(fun_facts, file1, indent=4)
            rand_fact = self._randomizer(fun_facts)
            return rand_fact
        else:
            new_facts = self._update_facts(fun_facts)
            rand_fact = self._randomizer(new_facts)
            return rand_fact
    
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
        for ar_name_idx, name in tqdm(enumerate(all_names), total=len(all_names), desc='Processing Names of Allah', colour='green', unit='MB'):
            html_contents = await asyncio.gather(
                            *[extract_content(endpoint=name, 
                                            slash=True, class_=i) 
                            for i in ('name-meaning', 'summary', 
                                    'column-section', 'second-section')]
                            )
            org_names = _fixer(True)
            all_name_contents[org_names[ar_name_idx]] = _extract_name_data()
        return all_name_contents
    
    async def extract_allah_contents(self, export=False):
        all_contents = await self._get_name_contents()
        merged_contents = {}
        for idx, (name, information) in enumerate(all_contents.items(), start=1):
            merged_contents[idx] = {
                                    'Name': name,
                                    'Information': {**information}
                                    }
        if export:
            with open(self.path / 'jsons' / 'list_allah_names.json', mode='w', encoding='utf-8') as file:
                json.dump(merged_contents, file, indent=4)
        return merged_contents
    
    # async def get_islamic_history(self):
    #     #?> Obtain contents for each chapter/book separately then merge
    #     #?> Make one class that does it all with given parameters (index, page) to parse all chapters at once
    #     #?> Experiment with each first for accurate results
    #     #**Book 1
    #     file = open(self.path / 'pdfs' / 'The Venture of Islam (Vol. 1).pdf', mode='rb')
    #     pdf_file = extract_pages(file)
    #     pdf_contents_ = ' '.join([j.get_text() for i in pdf_file for j in i if hasattr(j, 'get_text')])
    #     # chapter = re.escape(f'Chapter 1: {pdf_contents_[0]}# ')
    #     # pdf_contents = ' '.join(pdf_contents_)
    #     token_ = [word_tokenize(i.lower()) for i in pdf_contents_.split(' ')]
    #     model = Word2Vec(sentences=token_, vector_size=50, window=5, min_count=1, sg=0)
    #     find_word = 'islam'
    #     similar_words = model.wv.most_similar_cosmul(find_word)

    #     # Print similar words
    #     print(f"Similar words to '{find_word}':")
    #     for word, score in similar_words:
    #         print(f"{word}: {score}")
    
    async def good_manners(self):
        async def _get_all_manners():
            main_endpoint = '14618/good-manners-in-the-quran/'
            soup = await self._extract_contents(endpoint=main_endpoint,
                                                slash=True, url=main_url, 
                                                tag_='li')
            list_manners = [i.text for i in soup if i.text[0].isalpha()][2:]
            packed = [i.split('(') for i in list_manners]
            all_manners = {
                        idx: {
                                'manner': manner.rstrip(),
                                'verse': verse.strip(')')
                            }
                            for idx, (manner, verse) in enumerate(packed, start=1)}
            return all_manners

        main_url = self.url.islam_city
        all_manners = await _get_all_manners()
        queries = 'quransearch/index.php?q='        
        return all_manners
    
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
    def __init__(self):
        super().__init__()
    
    async def extract_qibla_data(self, **kwargs):
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
        
        export = kwargs.get('export', False)
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
            with open(self.path / 'jsons' / 'qibla_data.json', mode='w', encoding='utf-8') as file:
                json.dump(qibla_data, file, indent=4)
                file.close()
            return qibla_data
        else:
            return qibla_data


class Prophets(QuranAPI):
    def __init__(self):
        super().__init__()
    
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

            # Create a tqdm progress bar for the tasks
            tasks_description = "Processing Prophets"
            with tqdm(total=len(tasks), desc=tasks_description, colour='green', unit='MB') as pbar:
                async def run_task(task):
                    result = await task
                    pbar.update(1)  # Update the progress bar
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
                json.dump(all_contents, file, indent=4)
            return all_contents
        return all_contents

class IslamHindi(QuranAPI):
    def __init__(self):
        super().__init__()
    
    def _get_volume(self, file):
        pdf = open(self.path / 'pdfs' / f'{file}.pdf', mode='rb')
        return pdf
    
    @staticmethod
    def extractor(pdf, **kwargs):
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
    
    
    async def volume_1(self):
        def _get_page_index(contents, search=False, text=False):
            if search:
                return [idx for idx, i in enumerate(contents) if len(i)==1 and re.search(r'\d{1}', i)]
            if text:
                return [idx if not text else (idx, i) for idx, i in enumerate(contents) if re.match(r'(?:\d{1}\s\w+)|(?:\d{1,2}th\s\w+)', i)]
        
        def _cleaner(contents, finisher=False, index=None):
            left, right = index if index else (None, None)
            if not finisher:
                return ' '.join([contents.pop(idx) if re.match(r'\d{1}', i) else i.strip() for idx, i in enumerate(contents)])
            else:
                updated_contents_ = contents[left[0]+1: right[0]]
                cleaned_contents = _cleaner(updated_contents_)
                completed_contents = {left[1]: cleaned_contents}
                return completed_contents
        
        #**Table of Contents
        async def _get_toc():
            toc_pdf = self.extractor(pdf)
            toc_contents = {idx: element for (idx, element) in enumerate([i for i in
                                                                        toc_pdf[toc_pdf.index('Contents')+1:toc_pdf.index('ROODAD OF FIRST IJTEMA')-1]
                                                                        if not i.startswith('(')], start=1)}
            return toc_contents
        
        async def _title_page():
            title_page_ = self.extractor(pdf, maxpages=1)
            title_page = [i for i in title_page_ if re.search(r'^[a-zA-Z]', i)]
            return title_page
        
        async def _first_chap():
            def _first_sec():
                first_sec_contents = self.extractor(pdf, page_numbers=[2,3])
                left, right = _get_page_index(first_sec_contents, search=True)
                roodad_of_first_ijtema = ' '.join(first_sec_contents[left+1:right])
                key_ = ''.join(roodad_of_first_ijtema[:21])
                roodad_of_first_ijtema = roodad_of_first_ijtema.replace(key_, '')
                first_sec = {key_: roodad_of_first_ijtema}
                #?> Return tuple instead and convert all to dictionary later?
                return first_sec
            
            def _second_sec():
                def _sec_first_section():
                    second_first_contents = self.extractor(pdf, page_numbers=range(3, 12))
                    left, right = _get_page_index(second_first_contents, search=True)[:2]
                    proceedings_contents = second_first_contents[left+1:right]
                    proceedings = proceedings_contents[0].rstrip()
                    left, right = _get_page_index(proceedings_contents, text=True)
                    updated_contents_ = proceedings_contents[left[0]:right[0]]
                    sec_sub_section = updated_contents_.pop(0)
                    second_first_contents = {proceedings: {sec_sub_section: ''.join(updated_contents_)}}
                    return second_first_contents
                
                def _sec_second_section():
                    second_sec_contents = self.extractor(pdf, page_numbers=range(3, 10))
                    indexes = _get_page_index(second_sec_contents, search=False, text=True)[1:]
                    second_second_contents = _cleaner(second_sec_contents, finisher=True, index=indexes)
                    return second_second_contents
                
                def _sec_third_section():
                    second_third_contents = self.extractor(pdf, page_numbers=range(9, 18))
                    indexes = _get_page_index(second_third_contents, search=False, text=True)
                    second_third_contents = _cleaner(second_third_contents, finisher=True, index=indexes)
                    return second_third_contents
                
                def _sec_fourth_section():
                    second_fourth_contents = self.extractor(pdf, page_numbers=range(17, 29))
                    #** indexes: [[(21, '4 Shabaan'), (434, '5th SHABAAN')]]
                    #** numerals: [[(27, 'DIVISION OF WORK'),
                    #**             (30, 'I) Department of ILM and TAALIM (Knowledge and Education)'),
                    #**             (66, 'II) Department of NASHR o ISHAAT   (PRESS & PUBLICITY)'),
                    #**             (90, 'III)  Department  of  TANZEEM  E  JAMAAT  (Organization of '),
                    #**             (127, '(IV) Department of FINANCE'),
                    #**             (214, '(V)  Department  of  DAWAT  &  TABLIGH  (Preaching  and Propagation)')]]
                    indexes = _get_page_index(second_fourth_contents, search=False, text=True)
                    shabaa_index = indexes[0]
                    numerals = [(idx, i) for idx, i in enumerate(second_fourth_contents) if re.search(r'(?:I{1,3}\))|(?:I?V)', i)]
                    div_work = second_fourth_contents[numerals[0][0]:numerals[0][0]+3][1:]
                    shabaan_contents = ''.join(second_fourth_contents[shabaa_index[0]+1:shabaa_index[0]+6]+[' ']+div_work+['.'])
                    first_numeral_contents = second_fourth_contents[numerals[1][0]:numerals[2][0]]
                    first_numeral_key = first_numeral_contents.pop(0)
                    second_numeral_contents = second_fourth_contents[numerals[2][0]:numerals[3][0]]
                    second_numeral_key = second_numeral_contents.pop(0)
                    third_numeral_contents = second_fourth_contents[numerals[3][0]:numerals[4][0]]
                    third_numeral_key = third_numeral_contents.pop(0)
                    fourth_numeral_contents = second_fourth_contents[numerals[4][0]:numerals[5][0]-1]
                    fourth_numeral_key = fourth_numeral_contents.pop(0)
                    fourth_numeral_middle = fourth_numeral_contents[:fourth_numeral_contents.index('22')+5]
                    fourth_numeral_last = [fourth_numeral_contents.pop(-i) for i in range(4,0,-1)]
                    fourth_numeral_merged = [i for i in fourth_numeral_middle + fourth_numeral_last if not re.match(r'\d{2}',i)]
                    fifth_numeral_contents = second_fourth_contents[numerals[-1][0]:numerals[-1][0]+30]
                    fifth_numeral_key = fifth_numeral_contents.pop(0) + fifth_numeral_contents.pop(0)
                    guidance_contents = second_fourth_contents[numerals[-1][0]+31:][:-2]
                    guidance_key = guidance_contents.pop(0)
                    _ = [guidance_contents.pop(idx) for idx, i in enumerate(guidance_contents) if re.match(r'\d{2}', i)]
                    fifth_shabaan = second_fourth_contents[indexes[-1][0]:][:-2]
                    fifth_shabaan_key = fifth_shabaan.pop(0)
                    
                    shabaan = {shabaa_index[1]:
                                                {
                                                'Intro':shabaan_contents,
                                                first_numeral_key: first_numeral_contents,
                                                second_numeral_key: second_numeral_contents,
                                                third_numeral_key: third_numeral_contents,
                                                fourth_numeral_key: fourth_numeral_merged,
                                                fifth_numeral_key: fifth_numeral_contents,
                                                guidance_key: guidance_contents,
                                                fifth_shabaan_key: fifth_shabaan
                                                }}
                    return shabaan
                return (_sec_first_section(), _sec_second_section(), _sec_third_section(), _sec_fourth_section())
            return (_first_sec(), _second_sec())

        
        
        pdf = self._get_volume('En-Roodad-Vol1')
        toc, title, first_chap = await asyncio.gather(
                        _get_toc(),
                        _title_page(),
                        _first_chap()
                        )
        
        # first_chap = await _first_chap()
        # toc_contents = _get_toc()
        # title_page = _title_page()
        return title

async def main():
    # a = QuranAPI()
    # b = HadithAPI()
    # c = IslamFacts()
    # d = PrayerAPI()
    # e = Prophets()
    f = IslamHindi()
    
    async def run_all():
        tasks = [asyncio.create_task(task) for task in [
                    # a.extract_surahs(export=True),
                    # b.get_hadith(parser=True),
                    # c.extract_allah_contents(export=True),
                    # d.extract_qibla_data(export=True),
                    # c.fun_fact(limit=18),
                    # c.good_manners(),
                    # e.extract_all_prophets(export=False)
                    f.volume_1()
                    ]]
        results = await asyncio.gather(*tasks)
        return results
    
    start = time()
    results = await run_all()
    end = time()
    pprint(results)
    timer = (end-start)
    minutes, seconds = divmod(timer, 60) 
    print(f"Execution Time: {minutes:.0f} minutes and {seconds:.5f} seconds")

if __name__ == '__main__':
    asyncio.run(main())

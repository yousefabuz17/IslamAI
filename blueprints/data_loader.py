
import re
import json
import asyncio
import pandas as pd
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass
from collections import OrderedDict
from multiprocessing import cpu_count
from nested_lookup import nested_lookup as nested
from concurrent.futures import (ThreadPoolExecutor, as_completed)
from typing import (AnyStr, Dict, Generator, IO, ItemsView, KeysView, List, Optional, Tuple, Union, ValuesView)


def return_repr(method) -> str:
    def wrapper(self):
        return self.__repr__()
    return wrapper

@dataclass
class ArgMapper:
    def __init__(self, dict_, dont_map: bool=False, paths: Optional[List]=None) -> None:
        '''
        Initialize an ArgMapper instance.

        Args:
            dict_ (T): A Key-Value pair dictionary to be mapped to attributes of the ArgMapper instance.
            dont_map (bool, optional): If True, the dictionary won't be mapped as attributes (default is False).
            paths: Additional paths, ignored when `dont_map` is False.

        Important Notes:
            - If `dont_map` is True, and paths are provided, paths will be added to the ArgMapper instance as attributes.

        '''
        self.dict_ = dict_
        self._gen_files = ((k,v) for k,v in dict_.items())
        if dont_map and paths:
            for path in paths: 
                file_name = path.stem
                self._gen_files[file_name] = path
        for key, value in dict_.items():
            setattr(self, key, value)
    
    def __str__(self) -> str:
        keys = [i for i, _j in self._gen_files]
        if len(keys)!=0:
            return f'{keys}'
        return self.__repr__()

    def __repr__(self) -> str:
        return f'''
        1. To Obtain contents of files, use the name of the file as the attribute name.
        2. If no files are shown, iterate through `get_files` property for all files (PosixPaths)
            2a. Make sure parent directory only contains files w/o file extensions
            2b. If no files are shown then check directory path and make sure .
        3. If instance from DataLoader contains directories, then ArgMapper will not funciton properly {{will only contain directory paths}}
        [ATTRIBUTES ({self.__class__.__name__} instance)]
        {dir(self)}
        '''
    
    @property
    def get_files(self) -> Generator[Tuple, None, None]:
        return self.items()
    
    def get(self, key, default=None) -> Dict:
        try:
            return getattr(self, key)
        except AttributeError:
            return default
    
    def keys(self) -> KeysView:
        return self.dict_.keys()
    
    def values(self) -> ValuesView:
        return self.dict_.values()
    
    def items(self) -> ItemsView:
        return self.dict_.items()

    def __getitem__(self, key):
        return self.get(key)
    
    def __getattr__(self, key) -> Dict:
        if key in self.dict_:
            self.dict_[key]
        else:
            raise AttributeError(f'''
            \033[1;31m [{self.__class__.__name__} INSTANCE CONTAINS DIRECTORIES! MAPPING WILL NOT WORK]\033[0m
            {self.__repr__()}''')

class DataLoader(ArgMapper):
    def __init__(self, folder_path='jsons', file_ext: Optional[AnyStr]='json', ext_path='') -> Union[Dict, ArgMapper]:
        '''
        Initializes a data loader for Islamic data processing.

        This class is designed to load data for Islamic data processing purposes. It allows you to specify the `folder_path` where the data is stored. If the data is stored in an external directory, you can provide the `ext_path`.

        Parameters:
            - folder_path (T): A path to the directory containing the data. Use 'jsons' for Islamic data or a custom path for external data.
            - file_ext (str): The file extension of the data files (default is 'json').
            - ext_path (str): An optional path for external data directories.

        Returns:
            - Union[OrderedDict, ArgMapper]: The loaded data in the form of an OrderedDict or ArgMapper, depending on the use case.

        Important Notes:
            1) Use `folder_path` for Islamic data processing purposes (e.g., 'jsons/quran/altafsir').
                a) To load external data, specify the `ext_path` attribute.
            2) Mapping (`ArgMapper instance`) will only work if directory contains no sub-directories and only files
        '''
        self.ext_path = ext_path
        self.file_ext = file_ext
        self.path = MAIN_DIR / folder_path if not self.ext_path else Path(self.ext_path)
        self._data_files = self._get_all_files()

    def _get_all_files(self) -> Generator[Path, None, None]:
        return self.path.rglob(f'*.{self.file_ext}' if not all([self.ext_path, self.file_ext]) else '*')
    
    @property
    def get_files(self) -> Generator[Path, None, None]:
        return self._data_files
    
    def __str__(self) -> str:
        files = [i.name for i in self.get_files]
        if len(files)!=0:
            return f"{files}"
        return self.__repr__()
    
    def __repr__(self) -> str:
        return f'''
        Options to obtain file contents:
            1. Turn DataLoader to ArgMapper -> 
                i. pass argument `mapper` when calling loader (e.g DataLoader(dict_, **kwargs)(mapper=True))
                ii. use .mapper property for conversion (e.g DataLoader(dict_, **kwargs).mapper)
            2. Iterate through `get_files` method if folder contains directories
            3. If no files are shown, check directory path
        [ATTRIBUTES ({self.__class__.__name__} instance)]
        {dir(self) + [i.stem for i in self._get_all_files()]}
        '''

    def keys(self) -> str:
        return [i.stem for i in self._get_all_files()]
    
    @return_repr
    def values(self) -> str:
        pass
    
    @return_repr
    def items(self) -> str:
        pass
    
    @staticmethod
    def add(*args: Dict, mapper: bool=False, **kwargs) -> Union[Dict, ArgMapper]:
        '''
        Args:
        *args (dict): Multiple dictionaries to be added to the data loader. The order of dictionaries should correspond to their respective keys in the **kwargs.
        mapper (bool, optional): If True, the added dictionaries will be converted into an ArgMapper instance (default is False).

        Keyword Args:
            **kwargs: Specify the key names for each added dictionary. These keys are used as attributes for retrieval.

        Returns:
            Union[Dict, ArgMapper]: The added dictionaries with keys, or an ArgMapper instance if `mapper` is True.

        Example:
            To add dictionaries and specify key names for retrieval:

                ~ files = DataLoader.add(dict1, dict2, key1='file1', key2='file2')

        Important Notes:
            - If `mapper` is True, the method returns an ArgMapper instance.
            - If len(args) != len(kwargs)
                ~ kwargs = range(1, len(args)+1) by default (Will override any given kwargs)
            - The order of *args should respectively match the order of keys in **kwargs.
        '''
        all_folder_names = [str(i) for i in range(1, len(args)+1)] if (not kwargs or len(args)!=kwargs) else tuple(kwargs.values())
        all_added_files = {folder_name: folder_files for folder_name, folder_files in zip(all_folder_names, args)}
        if mapper:
            return ArgMapper(all_added_files)
        return all_added_files

    def load_data(self, file_path) -> Union[Dict, List[str]]:
        def json_map():
            try:
                return json.load(open(self.path / f'{file_name}.{self.file_ext}', encoding='utf-8'))
            except FileNotFoundError:
                raise FileNotFoundError(f"Data file not found at {file_name}")
            except json.JSONDecodeError as e:
                raise ValueError(f"Error decoding JSON in {file_name}: {e}")
        
        def ext_map():
            '''Mainly for readable files without any extension (e.g NLTK stopworks: corpora/stopwords/*)'''
            try: return open(self.path / file_name, encoding='utf-8').read().splitlines()
            except FileNotFoundError: raise FileNotFoundError(f"Data file not found at {file_name}")
        
        file_name = file_path.stem 
        data = json_map() if not self.ext_path else ext_map()
        return file_name, data

    def __call__(self, mapper: bool=False) -> Union[Dict, ArgMapper]:
        #** Using OrderedDict to maintain files in chronological order as they appear in the directory.
        all_files = OrderedDict()
        all_file_paths = []
        with ThreadPoolExecutor(max_workers=cpu_count() // 2) as executor:
            future_to_file = {executor.submit(self.load_data, file_path): file_path for file_path in self._data_files}
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                all_file_paths.append(file_path)
                try:
                    file_name, data = future.result()
                    all_files[file_name] = data
                except Exception: ...
        contains_dirs = all([i.is_dir() for i in all_file_paths])
        if mapper and not contains_dirs:
            return ArgMapper(all_files)
        elif contains_dirs:
            return ArgMapper(all_files, dont_map=True, paths=all_file_paths)
        return self

    @staticmethod
    def load_file(path='', file_name: AnyStr='', ext: AnyStr='json', **kwargs) -> Union[IO, Dict]:
        default_values = ('r', None)
        mode, encoding = tuple(kwargs.get(key, default_values[i]) for i,key in enumerate(('mode','encoding')))
        '''
        path='', file_name='', mode='r', encoding='utf-8', ext='json'
        Returns:
        - For JSON files: the loaded json file.
        - For PDF files: ommit mode when etx is PDf
        '''
        mode = 'rb' if ext=='pdf' else mode
        file_name = f'{file_name}.{ext}'
        file = open(MAIN_DIR / path / file_name, mode=mode, encoding=encoding)
        if ext=='json':
            file = json.load(file)
        return file

    @property
    def mapper(self) -> ArgMapper:
        return self(mapper=True)

class CSVProcessor:
    _dataframes = None
    
    def __init__(self):
        '''
        Initializes a CSV data processing class for this project.

        This class is designed for processing CSV data specific to this project.
        It relies on the global `JSONS` variable to access and manipulate data.
        Ensure that `JSONS` is properly configured before using this class.

        Note: This class does not return any specific data in its constructor, but it provides methods to retrieve the CSV data.
        '''
        pass
    
    def __str__(self) -> str:
        return f'{dir(self)}'
    
    def __repr__(self) -> str:
        return f'{self._get_methods(removeprefix=True)}'
    
    @return_repr
    def keys(self):
        pass
    
    @return_repr
    def values(self):
        pass
    
    @return_repr
    def items(self):
        pass
    
    @staticmethod
    def flatten(lst: List):
        for i in lst:
            if isinstance(i, list):
                yield from i
    
    async def process_surahs_info(self):
        surah_quran = JSONS.jsons['all-surahs-surahquran']
        surahs_info = OrderedDict({re.sub(r'(^\d{1,3}\-)|\'','',key): {k: v for k, v in values.items() if k not in ['verses', 'quran-source']} for key, values in surah_quran.items()})
        df = []
        for surah_name, surah_info in surahs_info.items():
            row_data = OrderedDict({'chapter_id': surah_info.pop('id'),
                                    'chapter': surah_name,
                                    'name_simple': surah_info.pop('name_simple'),
                                    'name_complex': surah_info.pop('name_complex'),
                                    'surah_name_ar': surah_info.pop('surah_name_ar')[::-1],
                                    'name_translation': surah_info.pop('name_translation'),
                                    **{k: str(v) if isinstance(v, int) else ' '.join(v).replace('\n','').strip() if isinstance(v, list) else v for k,v in surah_info.items()}})
            df.append(row_data)
        return pd.DataFrame(df)

    async def process_surahquran(self):
        surah_quran, verse_meanings = tuple(JSONS.jsons.get(i) for _,i in enumerate(('all-surahs-surahquran', 'all-surah-meanings')))
        verseID_meanings = OrderedDict({j['verse-id']: None if not j['description'][0] else ' '.join(j['description']) for i in nested('verse-info', verse_meanings) for j in i})
        all_surah_names = [re.sub(r'(^\d{1,3}\-)|\'','',i) for i in surah_quran.keys()]
        all_lang_verses = OrderedDict({all_surah_names[idx]: {**info['verses']} for idx, (_, info) in enumerate(surah_quran.items())})
        df = []
        for surahID, (surah_name, surah_info) in enumerate(all_lang_verses.items(), start=1):
            for lang, verses in surah_info.items():
                for idx, (_, verse) in enumerate(verses.items(), start=1):
                    verseID = f'[{surahID}:{idx}]'
                    row_data = OrderedDict({'ChapterID': surahID,
                                            'Chapter': surah_name,
                                            'Language': lang,
                                            'VerseID': verseID,
                                            'Verse': verse[::-1] if lang=='Arabic' else verse,
                                            'Description': verseID_meanings.get(verseID)})
                    df.append(row_data)
        return pd.DataFrame(df)
    
    async def process_allahs_names(self):
        allahs_names = JSONS.jsons.list_allah_names
        _ = allahs_names.pop('All Names')
        df = []
        for nameID, name_info in allahs_names.items():
            info_data = name_info['Information']
            all_names_info = OrderedDict({'ID': nameID,
                                    'Name': name_info.pop('Name'),
                                    'transliteration_eng': info_data.pop('transliteration_eng'),
                                    'transliteration_ar': info_data.pop('transliteration_ar')[::-1],
                                   **{k: v.replace('\n','').strip() for k,v in info_data.items()}})
            df.append(all_names_info)
        return pd.DataFrame(df)
    
    async def process_islamic_laws(self):
        islamic_laws = JSONS.jsons['islamic-laws']
        df = []
        for _, laws in islamic_laws.items():
            cat, laws = laws[0], laws[1]
            category = re.findall(r'\((.*?)\)', cat)[0]
            law_content = OrderedDict({'Category': category,
                                      **laws})
            df.append(law_content)
        return pd.DataFrame(df)
    
    async def process_islamic_terms(self):
        islamic_terms = JSONS.jsons['islamic-terms']
        df = []
        for i in islamic_terms:
            for letter, letter_info in i.items():
                if not letter_info:
                    letter_info = [OrderedDict({'Letter': letter,
                                            **{key: None for key in enumerate(('Term', 'Definition'))}})]
                for j in letter_info:
                    term, defintion = tuple(j.get(i) for _,i in enumerate(('Term', 'Definition')))
                    content = OrderedDict({
                                        'Letter': letter,
                                        'Term': term,
                                        'Definition': defintion})
                    df.append(content)
        return pd.DataFrame(df)
    
    async def process_proph_muhammeds_names(self):
        muhammads_names = JSONS.jsons.list_of_prophet_muhammed_names
        muhammads_names.pop('Source')
        all_names = [OrderedDict(**j) for _, i in muhammads_names.items() for j in list(i.values())]
        return pd.DataFrame(all_names, index=list(range(1, 100)))
    
    async def process_islamic_facts(self):
        islamic_facts = JSONS.jsons['islamic-facts']
        intro_fact = nested('Introduction', islamic_facts)
        facts = [list(i.values()) for i in nested('Facts', islamic_facts)]
        fixed_facts = [i if isinstance(i, str) else ''.join(i) for i in self.flatten(facts)]
        all_facts = intro_fact + fixed_facts
        
        return pd.DataFrame({'Facts': all_facts})
    
    async def process_islamic_timeline(self):
        islamic_timeline = JSONS.jsons['islamic-timeline']
        islamic_timeline.pop('Credits')
        centuries = [re.search(r'(?:\d{3,4})',i).group() for i in self.flatten(islamic_timeline.values())]
        centuries_info = [i.split('-')[-1].strip() for i in self.flatten(islamic_timeline.values())]
        full_timeline = OrderedDict({
                                    'Century': centuries,
                                    'Event': centuries_info})
        return pd.DataFrame(full_timeline)
    
    async def process_rabbana_duas(self):
        duas = JSONS.jsons['all-duas']
        rabbana_key = list(duas.keys())[0]
        rabbana_duas = [i[1] for i in duas[rabbana_key].items()]
        return pd.DataFrame(rabbana_duas, index=list(range(1, len(rabbana_duas)+1)))
    
    async def process_dua_categories(self):
        dua_categories = JSONS.jsons['all-duas']
        dua_key = list(dua_categories.keys())[1]
        dua_cats = [i[1] for i in dua_categories[dua_key].items()]
        return dua_cats
    
    async def process_qibla(self):
        qibla_content = JSONS.jsons.qibla_data
        return pd.DataFrame([{**i} for _,i in qibla_content.items()])
    
    async def process_quran_stats(self):
        stats = [{i:j for i,j in JSONS.jsons.quran_stats.items()}]
        return pd.DataFrame(stats)
    
    async def process_arabic_numbers(self):
        table = JSONS.arabic.arabic_numbers
        df = [j for _,j in nested('Table', table)[0].items()]
        return pd.DataFrame(df)
    
    async def execute_all(self):
        method_names = self._get_methods()
        all_dataframes = await asyncio.gather(*[getattr(self, csv_method)() for csv_method in method_names])
        all_df_methods = ArgMapper({method.removeprefix('process_'): df for method,df in zip(method_names, all_dataframes)})
        return all_df_methods
    
    def _get_methods(self, removeprefix=False):
        return [i if not removeprefix else i.removeprefix('process_') for i in dir(CSVProcessor) if re.match(r'^process', i) and asyncio.iscoroutinefunction(getattr(self, i))]
    
    @classmethod
    def dataframes(cls):
        '''
        Returns ArgMapper: An instance containing dataframes.
        
        Use attribute names to retrieve DataFrame objects (instances of pd.DataFrame).
        '''
        
        if cls._dataframes is None:
            cls._dataframes = asyncio.run(cls().execute_all())
        return cls._dataframes

@lru_cache(maxsize=1)
def loader(key: Optional[AnyStr]=None):
    '''
    key -> folder name: Optional[str] = None (Loads all JSON files)
    This function is mainly for this projects data rather for external use.
    Otherwise use DataLoader (dl) ext_path argument if needed.
    (E.g dl(ext_path=f'{Path.home()}/nltk_data/corpora/stopwords)(mapper: bool=False))
    
    Returns ArgMapper instance of folder for given key name.
    
    E.g
    all_hadiths = loader(key='hadiths')
    all_hadiths.<file_name> or use regular dictionary `get` methods including brackets
    
    To return all folders at once (Temporary folder name can be changed to personal liking), simply do:
    {folder: loader(key=folder) for _,folder in enumerate(<all_folder_names>)}
    '''
    # py3_12 = ArgMapper({folder: DataLoader(folder_path=f'{_JSONS}{'/' if folder==_JSONS else f'/{folder}'}').mapper for folder in FOLDERS})
    _folders = ArgMapper({folder: DataLoader(folder_path='{}{}'.format(_JSONS, '/' if folder==_JSONS else f'/{folder}')).mapper for folder in FOLDERS})
    if not key:
        #** loads all folders by default as ArgMapper
        return _folders
    return _folders.get(key, KeyError(f'Key `{key}` not found (Check folder name)'))

#^ Data Folder Path
_JSONS = 'jsons'
MAIN_DIR = Path(__file__).parent.parent.absolute() / 'islamic_data'
#^ All Folder Names (Using `all-surah(s)-*` files for quran directory)
_EXCLUDE = re.compile(r'(?!quran)')
FOLDERS = [_JSONS, *[i.name for i in Path(MAIN_DIR / _JSONS).glob('*') if i.is_dir() and _EXCLUDE.match(i.name)]]
#** All instances of ArgMapper 
#^ All NLTK Stopwords
STOPWORDS = DataLoader(ext_path=f'{Path.home()}/nltk_data/corpora/stopwords')
#^ All structured JSON files (JSONs + folders)
JSONS = loader()
#^ All structured CSV files (instances of pd.DataFrame)
CSVS = CSVProcessor.dataframes()

if __name__ == '__main__':
    # print(STOPWORDS)
    # print(JSONS)
    # print(CSVS)
    pass







#! Python 3.12
# import re
# import json
# import asyncio
# import pandas as pd
# from pathlib import Path
# from functools import lru_cache
# from dataclasses import dataclass
# from collections import OrderedDict
# from multiprocessing import cpu_count
# from nested_lookup import nested_lookup as nested
# from concurrent.futures import (ThreadPoolExecutor, as_completed)
# from typing import (AnyStr, Dict, Generator, IO, ItemsView, KeysView, List, Optional, Tuple, Union, ValuesView)


# def return_repr(method) -> str:
#     def wrapper(self):
#         return self.__repr__()
#     return wrapper

# @dataclass
# class ArgMapper[T: Dict]:
#     def __init__(self, dict_: T, dont_map: bool=False, paths: Optional[List]=None) -> None:
#         '''
#         Initialize an ArgMapper instance.

#         Args:
#             dict_ (T): A Key-Value pair dictionary to be mapped to attributes of the ArgMapper instance.
#             dont_map (bool, optional): If True, the dictionary won't be mapped as attributes (default is False).
#             paths: Additional paths, ignored when `dont_map` is False.

#         Important Notes:
#             - If `dont_map` is True, and paths are provided, paths will be added to the ArgMapper instance as attributes.

#         '''
#         self.dict_ = dict_
#         self._gen_files = ((k,v) for k,v in dict_.items())
#         if dont_map and paths:
#             for path in paths: 
#                 file_name = path.stem
#                 self._gen_files[file_name] = path
#         for key, value in dict_.items():
#             setattr(self, key, value)
    
#     def __str__(self):
#         keys = [i for i, _j in self._gen_files]
#         if len(keys)!=0:
#             return f'{keys}'
#         return self.__repr__()

#     def __repr__(self):
#         return f'''
#         1. To Obtain contents of files, use the name of the file as the attribute name.
#         2. If no files are shown, iterate through `get_files` property for all files (PosixPaths)
#             2a. Make sure parent directory only contains files w/o file extensions
#             2b. If no files are shown then check directory path and make sure .
#         3. If instance from DataLoader contains directories, then ArgMapper will not funciton properly {{will only contain directory paths}}
#         [ATTRIBUTES ({self.__class__.__name__} instance)]
#         {dir(self)}
#         '''
    
#     @property
#     def get_files(self) -> Generator[Tuple, None, None]:
#         return self.items()
    
#     def get(self, key, default=None) -> Dict:
#         try:
#             return getattr(self, key)
#         except AttributeError:
#             return default
    
#     def keys(self) -> KeysView:
#         return self.dict_.keys()
    
#     def values(self) -> ValuesView:
#         return self.dict_.values()
    
#     def items(self) -> ItemsView:
#         return self.dict_.items()

#     def __getitem__(self, key):
#         return self.get(key)
    
#     def __getattr__(self, key) -> Dict:
#         if key in self.dict_:
#             self.dict_[key]
#         else:
#             raise AttributeError(f'''
#             \033[1;31m [{self.__class__.__name__} INSTANCE CONTAINS DIRECTORIES! MAPPING WILL NOT WORK]\033[0m
#             {self.__repr__()}''')

# class DataLoader[T: Union[str, IO]](ArgMapper):
#     def __init__(self, folder_path: T='jsons', file_ext: Optional[AnyStr]='json', ext_path: T='') -> Union[Dict, ArgMapper]:
#         '''
#         Initializes a data loader for Islamic data processing.

#         This class is designed to load data for Islamic data processing purposes. It allows you to specify the `folder_path` where the data is stored. If the data is stored in an external directory, you can provide the `ext_path`.

#         Parameters:
#             - folder_path (T): A path to the directory containing the data. Use 'jsons' for Islamic data or a custom path for external data.
#             - file_ext (str): The file extension of the data files (default is 'json').
#             - ext_path (str): An optional path for external data directories.

#         Returns:
#             - Union[OrderedDict, ArgMapper]: The loaded data in the form of an OrderedDict or ArgMapper, depending on the use case.

#         Important Notes:
#             1) Use `folder_path` for Islamic data processing purposes (e.g., 'jsons/quran/altafsir').
#                 a) To load external data, specify the `ext_path` attribute.
#             2) Mapping (`ArgMapper instance`) will only work if directory contains no sub-directories and only files
#         '''
#         self.ext_path = ext_path
#         self.file_ext = file_ext
#         self.path = MAIN_DIR / folder_path if not self.ext_path else Path(self.ext_path)
#         self._data_files = self._get_all_files()

#     def _get_all_files(self) -> Generator[Path, None, None]:
#         return self.path.rglob(f'*.{self.file_ext}' if not all([self.ext_path, self.file_ext]) else '*')
    
#     @property
#     def get_files(self) -> Generator[Path, None, None]:
#         return self._data_files
    
#     def __str__(self) -> str:
#         files = [i.name for i in self.get_files]
#         if len(files)!=0:
#             return f"{files}"
#         return self.__repr__()
    
#     def __repr__(self) -> str:
#         return f'''
#         Options to obtain file contents:
#             1. Turn DataLoader to ArgMapper -> 
#                 i. pass argument `mapper` when calling loader (e.g DataLoader(dict_, **kwargs)(mapper=True))
#                 ii. use .mapper property for conversion (e.g DataLoader(dict_, **kwargs).mapper)
#             2. Iterate through `get_files` method if folder contains directories
#             3. If no files are shown, check directory path
#         [ATTRIBUTES ({self.__class__.__name__} instance)]
#         {dir(self) + [i.stem for i in self._get_all_files()]}
#         '''

#     def keys(self) -> str:
#         return [i.stem for i in self._get_all_files()]
    
#     @return_repr
#     def values(self) -> str:
#         pass
    
#     @return_repr
#     def items(self) -> str:
#         pass
    
#     @staticmethod
#     def add(*args: Dict, mapper: bool=False, **kwargs) -> Union[Dict, ArgMapper]:
#         '''
#         Args:
#         *args (dict): Multiple dictionaries to be added to the data loader. The order of dictionaries should correspond to their respective keys in the **kwargs.
#         mapper (bool, optional): If True, the added dictionaries will be converted into an ArgMapper instance (default is False).

#         Keyword Args:
#             **kwargs: Specify the key names for each added dictionary. These keys are used as attributes for retrieval.

#         Returns:
#             Union[Dict, ArgMapper]: The added dictionaries with keys, or an ArgMapper instance if `mapper` is True.

#         Example:
#             To add dictionaries and specify key names for retrieval:

#                 ~ files = DataLoader.add(dict1, dict2, key1='file1', key2='file2')

#         Important Notes:
#             - If `mapper` is True, the method returns an ArgMapper instance.
#             - If len(args) != len(kwargs)
#                 ~ kwargs = range(1, len(args)+1) by default (Will override any given kwargs)
#             - The order of *args should respectively match the order of keys in **kwargs.
#         '''
#         all_folder_names = [str(i) for i in range(1, len(args)+1)] if (not kwargs or len(args)!=kwargs) else tuple(kwargs.values())
#         all_added_files = {folder_name: folder_files for folder_name, folder_files in zip(all_folder_names, args)}
#         if mapper:
#             return ArgMapper(all_added_files)
#         return all_added_files

#     def load_data(self, file_path: T) -> Union[Dict, List[str]]:
#         def json_map():
#             try:
#                 return json.load(open(self.path / f'{file_name}.{self.file_ext}', encoding='utf-8'))
#             except FileNotFoundError:
#                 raise FileNotFoundError(f"Data file not found at {file_name}")
#             except json.JSONDecodeError as e:
#                 raise ValueError(f"Error decoding JSON in {file_name}: {e}")
        
#         def ext_map():
#             '''Mainly for readable files without any extension (e.g NLTK stopworks: corpora/stopwords/*)'''
#             try: return open(self.path / file_name, encoding='utf-8').read().splitlines()
#             except FileNotFoundError: raise FileNotFoundError(f"Data file not found at {file_name}")
        
#         file_name = file_path.stem 
#         data = json_map() if not self.ext_path else ext_map()
#         return file_name, data

#     def __call__(self: T, mapper: bool=False) -> Union[Dict, ArgMapper]:
#         #** Using OrderedDict to maintain files in chronological order as they appear in the directory.
#         all_files = OrderedDict()
#         all_file_paths = []
#         with ThreadPoolExecutor(max_workers=cpu_count() // 2) as executor:
#             future_to_file = {executor.submit(self.load_data, file_path): file_path for file_path in self._data_files}
#             for future in as_completed(future_to_file):
#                 file_path = future_to_file[future]
#                 all_file_paths.append(file_path)
#                 try:
#                     file_name, data = future.result()
#                     all_files[file_name] = data
#                 except Exception: ...
#         contains_dirs = all([i.is_dir() for i in all_file_paths])
#         if mapper and not contains_dirs:
#             return ArgMapper(all_files)
#         elif contains_dirs:
#             return ArgMapper(all_files, dont_map=True, paths=all_file_paths)
#         return self

#     @staticmethod
#     def load_file(path: T='', file_name: AnyStr='', ext: AnyStr='json', **kwargs) -> Union[IO, Dict]:
#         default_values = ('r', None)
#         mode, encoding = tuple(kwargs.get(key, default_values[i]) for i,key in enumerate(('mode','encoding')))
#         '''
#         path='', file_name='', mode='r', encoding='utf-8', ext='json'
#         Returns:
#         - For JSON files: the loaded json file.
#         - For PDF files: ommit mode when etx is PDf
#         '''
#         mode = 'rb' if ext=='pdf' else mode
#         file_name = f'{file_name}.{ext}'
#         file = open(MAIN_DIR / path / file_name, mode=mode, encoding=encoding)
#         if ext=='json':
#             file = json.load(file)
#         return file

#     @property
#     def mapper(self: T) -> ArgMapper:
#         return self(mapper=True)

# class CSVProcessor[T: ArgMapper[ArgMapper[Dict]]]:
#     _dataframes = None
    
#     def __init__(self: T) -> ArgMapper[pd.DataFrame]:
#         '''
#         Initializes a CSV data processing class for this project.

#         This class is designed for processing CSV data specific to this project.
#         It relies on the global `JSONS` variable to access and manipulate data.
#         Ensure that `JSONS` is properly configured before using this class.

#         Note: This class does not return any specific data in its constructor, but it provides methods to retrieve the CSV data.
#         '''
#         pass
    
#     def __str__(self) -> str:
#         return f'{dir(self)}'
    
#     def __repr__(self) -> str:
#         return f'{self._get_methods(removeprefix=True)}'
    
#     @return_repr
#     def keys(self):
#         pass
    
#     @return_repr
#     def values(self):
#         pass
    
#     @return_repr
#     def items(self):
#         pass
    
#     @staticmethod
#     def flatten(lst: List):
#         for i in lst:
#             if isinstance(i, list):
#                 yield from i
    
#     async def process_surahs_info(self: T) -> pd.DataFrame:
#         surah_quran = JSONS.jsons['all-surahs-surahquran']
#         surahs_info = OrderedDict({re.sub(r'(^\d{1,3}\-)|\'','',key): {k: v for k, v in values.items() if k not in ['verses', 'quran-source']} for key, values in surah_quran.items()})
#         df = []
#         for surah_name, surah_info in surahs_info.items():
#             row_data = OrderedDict({'chapter_id': surah_info.pop('id'),
#                                     'chapter': surah_name,
#                                     'name_simple': surah_info.pop('name_simple'),
#                                     'name_complex': surah_info.pop('name_complex'),
#                                     'surah_name_ar': surah_info.pop('surah_name_ar')[::-1],
#                                     'name_translation': surah_info.pop('name_translation'),
#                                     **{k: str(v) if isinstance(v, int) else ' '.join(v).replace('\n','').strip() if isinstance(v, list) else v for k,v in surah_info.items()}})
#             df.append(row_data)
#         return pd.DataFrame(df)

#     async def process_surahquran(self: T) -> pd.DataFrame:
#         surah_quran, verse_meanings = tuple(JSONS.jsons.get(i) for _,i in enumerate(('all-surahs-surahquran', 'all-surah-meanings')))
#         verseID_meanings = OrderedDict({j['verse-id']: None if not j['description'][0] else ' '.join(j['description']) for i in nested('verse-info', verse_meanings) for j in i})
#         all_surah_names = [re.sub(r'(^\d{1,3}\-)|\'','',i) for i in surah_quran.keys()]
#         all_lang_verses = OrderedDict({all_surah_names[idx]: {**info['verses']} for idx, (_, info) in enumerate(surah_quran.items())})
#         df = []
#         for surahID, (surah_name, surah_info) in enumerate(all_lang_verses.items(), start=1):
#             for lang, verses in surah_info.items():
#                 for idx, (_, verse) in enumerate(verses.items(), start=1):
#                     verseID = f'[{surahID}:{idx}]'
#                     row_data = OrderedDict({'ChapterID': surahID,
#                                             'Chapter': surah_name,
#                                             'Language': lang,
#                                             'VerseID': verseID,
#                                             'Verse': verse[::-1] if lang=='Arabic' else verse,
#                                             'Description': verseID_meanings.get(verseID)})
#                     df.append(row_data)
#         return pd.DataFrame(df)
    
#     async def process_allahs_names(self: T) -> pd.DataFrame:
#         allahs_names = JSONS.jsons.list_allah_names
#         _ = allahs_names.pop('All Names')
#         df = []
#         for nameID, name_info in allahs_names.items():
#             info_data = name_info['Information']
#             all_names_info = OrderedDict({'ID': nameID,
#                                     'Name': name_info.pop('Name'),
#                                     'transliteration_eng': info_data.pop('transliteration_eng'),
#                                     'transliteration_ar': info_data.pop('transliteration_ar')[::-1],
#                                    **{k: v.replace('\n','').strip() for k,v in info_data.items()}})
#             df.append(all_names_info)
#         return pd.DataFrame(df)
    
#     async def process_islamic_laws(self: T) -> pd.DataFrame:
#         islamic_laws = JSONS.jsons['islamic-laws']
#         df = []
#         for _, laws in islamic_laws.items():
#             cat, laws = laws[0], laws[1]
#             category = re.findall(r'\((.*?)\)', cat)[0]
#             law_content = OrderedDict({'Category': category,
#                                       **laws})
#             df.append(law_content)
#         return pd.DataFrame(df)
    
#     async def process_islamic_terms(self: T) -> pd.DataFrame:
#         islamic_terms = JSONS.jsons['islamic-terms']
#         df = []
#         for i in islamic_terms:
#             for letter, letter_info in i.items():
#                 if not letter_info:
#                     letter_info = [OrderedDict({'Letter': letter,
#                                             **{key: None for key in enumerate(('Term', 'Definition'))}})]
#                 for j in letter_info:
#                     term, defintion = tuple(j.get(i) for _,i in enumerate(('Term', 'Definition')))
#                     content = OrderedDict({
#                                         'Letter': letter,
#                                         'Term': term,
#                                         'Definition': defintion})
#                     df.append(content)
#         return pd.DataFrame(df)
    
#     async def process_proph_muhammeds_names(self: T) -> pd.DataFrame:
#         muhammads_names = JSONS.jsons.list_of_prophet_muhammed_names
#         muhammads_names.pop('Source')
#         all_names = [OrderedDict(**j) for _, i in muhammads_names.items() for j in list(i.values())]
#         return pd.DataFrame(all_names, index=list(range(1, 100)))
    
#     async def process_islamic_facts(self: T) -> pd.DataFrame:
#         islamic_facts = JSONS.jsons['islamic-facts']
#         intro_fact = nested('Introduction', islamic_facts)
#         facts = [list(i.values()) for i in nested('Facts', islamic_facts)]
#         fixed_facts = [i if isinstance(i, str) else ''.join(i) for i in self.flatten(facts)]
#         all_facts = intro_fact + fixed_facts
        
#         return pd.DataFrame({'Facts': all_facts})
    
#     async def process_islamic_timeline(self: T) -> pd.DataFrame:
#         islamic_timeline = JSONS.jsons['islamic-timeline']
#         islamic_timeline.pop('Credits')
#         centuries = [re.search(r'(?:\d{3,4})',i).group() for i in self.flatten(islamic_timeline.values())]
#         centuries_info = [i.split('-')[-1].strip() for i in self.flatten(islamic_timeline.values())]
#         full_timeline = OrderedDict({
#                                     'Century': centuries,
#                                     'Event': centuries_info})
#         return pd.DataFrame(full_timeline)
    
#     async def process_rabbana_duas(self: T) -> pd.DataFrame:
#         duas = JSONS.jsons['all-duas']
#         rabbana_key = list(duas.keys())[0]
#         rabbana_duas = [i[1] for i in duas[rabbana_key].items()]
#         return pd.DataFrame(rabbana_duas, index=list(range(1, len(rabbana_duas)+1)))
    
#     async def process_dua_categories(self: T) -> pd.DataFrame:
#         dua_categories = JSONS.jsons['all-duas']
#         dua_key = list(dua_categories.keys())[1]
#         dua_cats = [i[1] for i in dua_categories[dua_key].items()]
#         return dua_cats
    
#     async def process_qibla(self: T) -> pd.DataFrame:
#         qibla_content = JSONS.jsons.qibla_data
#         return pd.DataFrame([{**i} for _,i in qibla_content.items()])
    
#     async def process_quran_stats(self: T) -> pd.DataFrame:
#         stats = [{i:j for i,j in JSONS.jsons.quran_stats.items()}]
#         return pd.DataFrame(stats)
    
#     async def process_arabic_numbers(self: T) -> pd.DataFrame:
#         table = JSONS.arabic.arabic_numbers
#         df = [j for _,j in nested('Table', table)[0].items()]
#         return pd.DataFrame(df)
    
#     async def execute_all(self) -> ArgMapper[pd.DataFrame]:
#         method_names = self._get_methods()
#         all_dataframes = await asyncio.gather(*[getattr(self, csv_method)() for csv_method in method_names])
#         all_df_methods = ArgMapper({method.removeprefix('process_'): df for method,df in zip(method_names, all_dataframes)})
#         return all_df_methods
    
#     def _get_methods(self, removeprefix=False):
#         return [i if not removeprefix else i.removeprefix('process_') for i in dir(CSVProcessor) if re.match(r'^process', i) and asyncio.iscoroutinefunction(getattr(self, i))]
    
#     @classmethod
#     def dataframes(cls) -> ArgMapper[pd.DataFrame]:
#         '''
#         Returns ArgMapper: An instance containing dataframes.
        
#         Use attribute names to retrieve DataFrame objects (instances of pd.DataFrame).
#         '''
        
#         if cls._dataframes is None:
#             cls._dataframes = asyncio.run(cls().execute_all())
#         return cls._dataframes

# @lru_cache(maxsize=1)
# def loader(key: Optional[AnyStr]=None) -> ArgMapper[Dict]:
#     '''
#     key -> folder name: Optional[str] = None (Loads all JSON files)
#     This function is mainly for this projects data rather for external use.
#     Otherwise use DataLoader (dl) ext_path argument if needed.
#     (E.g dl(ext_path=f'{Path.home()}/nltk_data/corpora/stopwords)(mapper: bool=False))
    
#     Returns ArgMapper instance of folder for given key name.
    
#     E.g
#     all_hadiths = loader(key='hadiths')
#     all_hadiths.<file_name> or use regular dictionary `get` methods including brackets
    
#     To return all folders at once (Temporary folder name can be changed to personal liking), simply do:
#     {folder: loader(key=folder) for _,folder in enumerate(<all_folder_names>)}
#     '''
#     _folders = ArgMapper({folder: DataLoader(folder_path=f'{_JSONS}{'/' if folder==_JSONS else f'/{folder}'}').mapper for folder in FOLDERS})
#     if not key:
#         #** loads all folders by default as ArgMapper
#         return _folders
#     return _folders.get(key, KeyError(f'Key `{key}` not found (Check folder name)'))

# #^ Data Folder Path
# _JSONS = 'jsons'
# MAIN_DIR = Path(__file__).parent.parent.absolute() / 'islamic_data'
# #^ All Folder Names (Using `all-surah(s)-*` files for quran directory)
# _EXCLUDE = re.compile(r'(?!quran)')
# FOLDERS = [_JSONS, *[i.name for i in Path(MAIN_DIR / _JSONS).glob('*') if i.is_dir() and _EXCLUDE.match(i.name)]]
# #** All instances of ArgMapper 
# #^ All NLTK Stopwords
# STOPWORDS = DataLoader(ext_path=f'{Path.home()}/nltk_data/corpora/stopwords')
# #^ All structured JSON files (JSONs + folders)
# JSONS = loader()
# #^ All structured CSV files (instances of pd.DataFrame)
# CSVS = CSVProcessor.dataframes()

# if __name__ == '__main__':
#     # print(STOPWORDS)
#     # print(JSONS)
#     # print(CSVS)
#     pass
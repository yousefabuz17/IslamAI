import re
import ssl
import json
import asyncio
import pandas as pd
from pathlib import Path
from nltk import download
from dataclasses import dataclass
from itertools import chain
from collections import OrderedDict
from multiprocessing import cpu_count
from nested_lookup import nested_lookup as nested
from functools import (lru_cache, cached_property)
from concurrent.futures import (ThreadPoolExecutor, as_completed)
from typing import (Any, AnyStr, Dict, Generator, IO, ItemsView, KeysView,
                    List, Optional, Tuple, Union, ValuesView)
from pprint import pprint

#^ Primary path for accessing project-related data.
MAIN_DIR = Path(__file__).parents[1].absolute() / 'islamic_data'

@dataclass
class ArgMapper[T: Dict]:
    '''
        [MAPPING IS NOT SUPPORTED FOR DIRECTORIES]
        
        ~Argument MUST ONLY be a 2 key-value paired iterable
        1. To obtain contents of files, use the name of the file as the attribute name.
        2. If no files are shown, iterate through `get_files` property for all files (PosixPaths)
            2a. Make sure parent directory only contains files w/o file extensions
            2b. If no files are shown then check directory path and make sure .
        3. If instance from DataLoader contains directories, then ArgMapper will not function properly.
            3a. WILL RAISE AN ERROR
        4. If caching is involved (overrides contents which leads into errors)
    '''
    def __init__(self, dict_: T) -> None:
        '''
        Initialize an ArgMapper instance.

        Args:
            dict_ (T): A Key-Value pair dictionary or 2-Pair Iterable to be mapped to attributes of the ArgMapper instance.
        '''
        self.dict_: T = dict_
        self.__index = 0
        self._check_arg()
        self._set_attrs()
    
    def _set_attrs(self):
        try:
            for key, value in self.dict_.items():
                setattr(self, key, value)
        except (AttributeError, ValueError, TypeError):
            return self._check_arg(True)
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.__index >= len(self.dict_):
            raise StopIteration
        item = getattr(self, sorted(self.keys())[self.__index])
        self.__index += 1
        return item 
    
    def __len__(self) -> int:
        return len(self.dict_)
    
    def __str__(self) -> str:
        return f'{list(self.keys(True))}'

    def __repr__(self) -> str:
        return f'{dir(self)}'
    
    @property
    def get_files(self) -> Generator[Tuple, None, None]:
        return self.items()
    
    def _check_arg(self, __raise=False):
        '''This simply validates the arugment passed'''
        __message = f'ArgMapper constructor expects a dictionary or iterable as its argument. Argument may not be valid:\n`{self.dict_}`'
        if __raise:
            raise TypeError(__message)
        try:
            if not isinstance(self.dict_, Dict):
                raise TypeError(__message)
            _gen = (i for i, _j in self.get_files)
            if len(list(_gen))!=0:
                return _gen
        except (AttributeError, ValueError, TypeError):
            raise AttributeError(__message)
    
    def get(self, __key: AnyStr, __default: Optional[Any]=None) -> Union[Dict, AttributeError]:
        try:
            return getattr(self, str(__key))
        except AttributeError:
            return __default
    
    def keys(self, __sort=False) -> KeysView:
        return self.dict_.keys() if not __sort else sorted(self.dict_.keys())
    
    def values(self) -> ValuesView:
        return self.dict_.values()
    
    def items(self) -> ItemsView:
        return self.dict_.items()
    
    def __getitem__(self, __key: AnyStr) -> Union[Dict, AttributeError]:
        return self.get(__key)
    
    def __getattr__(self, __key: AnyStr) -> Union[Dict, AttributeError]:
        try:
            if str(__key) in self.dict_:
                self.dict_[__key]
        except TypeError: ...
    
    @property
    def reset(self) -> Dict:
        '''Resets ArgMapper back to Dictionary instance'''
        return self.dict_

class DataLoader[T: Union[IO[str], str]]:
    def __init__(self, folder_path: T='jsons', file_ext: Optional[AnyStr]='json', ext_path: T='') -> Union[Dict, ArgMapper]:
        '''
        This class is designed to load data for Islamic data processing purposes.
        It allows you to specify the `folder_path` where the data is stored.
        If the data is stored in an external directory, you can provide the `ext_path`.

        The DataLoader class serves as a fundamental component for efficiently loading all structured and clean data
        for this project.
        
        ### Parameters:
            - folder_path (T): A path to the directory containing the data. Use 'jsons' for Islamic data or a custom path for external data.
            - file_ext (str): The file extension of the data files (default is 'json').
            - ext_path (str): An optional path for external data directories.

        ### Returns:
            - Union[Dict, ArgMapper]: The loaded data in the instance of [Dict, ArgMapper], depending on the use case.

        ### Important Notes:
            1) Use `folder_path` for Islamic data processing purposes (e.g., 'jsons/quran/altafsir').
                a) To load external data, specify the `ext_path` attribute.
            2) Mapping with an ArgMapper instance will function correctly when the directory exclusively contains read-write files and does not include subdirectories.
                a) The presence of subdirectories may lead to issues in the mapping process and/or reading the files.
        '''
        self.folder_path: T = folder_path
        self.ext_path: T= ext_path
        self.file_ext = file_ext
        self.path: T = MAIN_DIR / folder_path if not self.ext_path else Path(self.ext_path)
        self._data_files: Generator[Path, None, Union[IO[str], AnyStr]] = self._get_all_files()

    def __len__(self) -> int:
        return len(list(self.get_files))
    
    def _get_all_files(self) -> Generator[Path, None, Union[IO[str], AnyStr]]:
        return self.path.rglob(f'*.{self.file_ext}' if not self.file_ext else '*')
    
    @property
    def file_names(self) -> List:
        return [i.name for i in self._get_all_files()]
    
    @property
    def get_files(self: Generator[AnyStr, None, None]) -> Dict:
        return OrderedDict({file.name: file for file in self._get_all_files()})
    
    def __str__(self) -> str:
        return f'{self.file_names}'
    
    def __repr__(self) -> str:
        _path = '/'.join(map(lambda i: Path(i).parts[-1], [self.folder_path] if not self.ext_path else [self.ext_path]))
        return f'''
        Options to obtain file contents:
            1. Turn DataLoader to ArgMapper -> 
                i. pass argument `mapper` when calling loader (e.g DataLoader(dict_, **kwargs)(mapper=True))
                ii. use .mapper property for conversion (e.g DataLoader(dict_, **kwargs).mapper)
            2. Iterate through `get_files`
            3. If no files are shown, check directory path
        [ATTRIBUTES for {_path} ({self.__class__.__name__} instance]
        {dir(self) + self.file_names}
        '''
    
    def get(self, __key: AnyStr, __default: Optional[Any]=None) -> Union[Dict, Optional[Any]]:
        if __key in self.get_files:
            return self.get_files[__key]
        return __default
    
    def __getattr__(self, __key: AnyStr) -> Union[Dict, AttributeError]:
        return self.get(__key, AttributeError(f'`{__key}` is not an attribute'))
    
    @staticmethod
    def add(*args: Dict, mapper: bool=False, **kwargs: IO[str]) -> Union[Dict, ArgMapper]:
        '''
        ### Args:
        :param *args Dict: Multiple dictionaries to be added to the data loader. The order of dictionaries should correspond to their respective keys in the **kwargs.
        :param mapper Optional[bool]: If True, the added dictionaries will be converted into an ArgMapper instance (default is False).

        ### Keyword Args:
            **kwargs: Specify the key names for each added dictionary. These keys are used as attributes for retrieval.

        ### Returns:
            >>> Union[Dict, ArgMapper]: The added dictionaries with keys, or an ArgMapper instance if `mapper` is True.

        ### Example:
            To add dictionaries and specify key names for retrieval:

                ~ files = DataLoader.add(dict1, dict2, key1='file1', key2='file2')

        ### Important Notes:
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

    @lru_cache(maxsize=None)
    def load_data(self, file_path: Union[IO[str], str]) -> Tuple[str, IO[str]]:
        def json_map() -> IO[str]:
            try:
                return json.load(open(self.path / f'{file_name}.{self.file_ext}', encoding='utf-8'))
            except FileNotFoundError as f_error:
                raise f_error(f"Data file not found for {file_name} at `{file_path}`")
            except json.JSONDecodeError as e:
                raise ValueError(f"Error decoding JSON for {file_name} at `{file_path}`: {e}")
        
        def ext_map() -> Union[List[str], FileNotFoundError]:
            '''Mainly for readable files without any extension (e.g NLTK stopworks: corpora/stopwords/*)'''
            try:
                return open(self.path / file_name, encoding='utf-8').read().splitlines()
            except FileNotFoundError as f_error:
                raise f_error(f"Data file not found at {file_name}")
        
        file_name = file_path.stem 
        data = json_map() if not self.ext_path else ext_map()
        return file_name, data

    def __call__(self, mapper: bool=False) -> Union[Dict, ArgMapper]:
        #** Using OrderedDict to maintain files in chronological order as they appear in the directory.
        all_files: Dict= OrderedDict()
        with ThreadPoolExecutor(max_workers=cpu_count() // 2) as executor:
            future_to_file = {executor.submit(self.load_data, file_path): file_path for file_path in self._data_files}
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    file_name, data = future.result()
                    all_files[file_name] = data
                except Exception: ...
        
        if mapper:
            return ArgMapper(all_files)
        return all_files
    
    @staticmethod
    def load_file(path: T='', file_name: AnyStr='', ext: AnyStr='json', **kwargs) -> Union[IO[str], Dict]:
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
        file = open(MAIN_DIR / path / file_name, mode=mode, encoding=encoding, **kwargs)
        if ext=='json':
            file = json.load(file)
        return file

    @property
    def mapper(self: T) -> ArgMapper:
        return self(mapper=True)

class CSVProcessor[T: ArgMapper[pd.DataFrame]]:
    '''The CSVProcessor class is designed for handling and processing CSV data within the context of this project.'''
    
    _dataframes = None
    
    def __init__(self) -> None:
        '''
        ### Args:
            None
        
        - This class is designed for processing CSV data specific to this project.
        - It relies on global variables to access and manipulate data.

        ### Note:
            >>> This class does not return any specific data in its constructor, but it provides methods to retrieve the CSV data.
        
        E.g
        To utilize this class, simply create an instance like this:
        - processor = CSVProcessor()
        - dataframes = processor.dataframes
        '''
        self._path = MAIN_DIR / 'csvs'
    
    def __str__(self) -> str:
        return f'{dir(self)}'
    
    def __repr__(self) -> str:
        return f'{self._get_methods()}'
    
    async def process_surahs_info(self) -> pd.DataFrame:
        surah_quran = JSONS['all-surahs-surahquran'] #type: ignore
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

    async def process_surahquran(self) -> pd.DataFrame:
        surah_quran, verse_meanings = tuple(JSONS.get(i) for _,i in enumerate(('all-surahs-surahquran', 'all-surah-meanings'))) #type: ignore
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
    
    async def process_allahs_names(self) -> pd.DataFrame:
        allahs_names = JSONS.list_allah_names #type: ignore
        allahs_names.pop('All Names')
        df = []
        for nameID, name_info in allahs_names.items():
            info_data = name_info['Information']
            all_names_info = OrderedDict({
                                    'ID': nameID,
                                    'Name': name_info.pop('Name'),
                                    'Transliteration_eng': info_data.pop('transliteration_eng'),
                                    'Transliteration_ar': info_data.pop('transliteration_ar')[::-1],
                                   **{k.title(): v.replace('\n','').strip() for k,v in info_data.items()}})
            df.append(all_names_info)
        return pd.DataFrame(df)
    
    async def process_islamic_laws(self) -> pd.DataFrame:
        islamic_laws = JSONS['islamic-laws'] #type: ignore
        df = []
        for _, laws in islamic_laws.items():
            cat, laws = laws[0], laws[1]
            category = re.findall(r'\((.*?)\)', cat)[0]
            law_content = OrderedDict({'Category': category,
                                      **laws})
            df.append(law_content)
        return pd.DataFrame(df)
    
    async def process_islamic_terms(self) -> pd.DataFrame:
        islamic_terms = JSONS['islamic-terms'] #type: ignore
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
    
    async def process_proph_muhammeds_names(self) -> pd.DataFrame:
        muhammads_names = JSONS.list_of_prophet_muhammed_names #type: ignore
        muhammads_names.pop('Source')
        all_names = [OrderedDict(**j) for _, i in muhammads_names.items() for j in i.values()]
        return pd.DataFrame(all_names, index=list(range(1, len(all_names)+1)))
    
    async def process_islamic_facts(self) -> pd.DataFrame:
        islamic_facts = JSONS['islamic-facts'] #type: ignore
        intro_fact = nested('Introduction', islamic_facts)
        facts = [list(i.values()) for i in nested('Facts', islamic_facts)]
        fixed_facts = [i if isinstance(i, str) else ''.join(i) for i in self.flatten(facts)]
        all_facts = intro_fact + fixed_facts
        return pd.DataFrame({'Facts': all_facts})
    
    async def process_islamic_timeline(self) -> pd.DataFrame:
        islamic_timeline = JSONS['islamic-timeline'] #type: ignore
        islamic_timeline.pop('Credits')
        centuries = [re.search(r'(?:\d{3,4})',i).group() for i in self.flatten(islamic_timeline.values())]
        centuries_info = [i.split('-')[-1].strip() for i in self.flatten(islamic_timeline.values())]
        full_timeline = OrderedDict({'Century': centuries,
                                    'Event': centuries_info})
        return pd.DataFrame(full_timeline)
    
    async def process_rabbana_duas(self) -> pd.DataFrame:
        duas = JSONS['all-duas'] #type: ignore
        rabbana_key = list(duas.keys())[0]
        rabbana_duas = [i[1] for i in duas[rabbana_key].items()]
        return pd.DataFrame(rabbana_duas, index=list(range(1, len(rabbana_duas)+1)))
    
    def process_dua_categories(self) -> pd.DataFrame:
        #! Finish
        dua_categories = JSONS['all-duas'] #type: ignore
        dua_key = list(dua_categories.keys())[1]
        dua_cats = [i[1] for i in dua_categories[dua_key].items()]
        return dua_cats
    
    async def process_qibla(self) -> pd.DataFrame:
        qibla_content = JSONS.qibla_data #type: ignore
        return pd.DataFrame([{**i} for _,i in qibla_content.items()])
    
    async def process_quran_stats(self) -> pd.DataFrame:
        stats = [{i:j for i,j in JSONS.quran_stats.items()}] #type: ignore
        return pd.DataFrame(stats)
    
    async def process_arabic_numbers(self) -> pd.DataFrame:
        table = ARABIC.arabic_numbers #type: ignore
        df = [j for _,j in nested('Table', table)[0].items()]
        return pd.DataFrame(df)
    
    async def execute_all(self) -> T:
        '''Main constructor to execute all methods for DataFrames (ArgMapper instance)'''
        method_names = self._get_methods
        async with asyncio.TaskGroup() as tg:
            df_tasks = [tg.create_task(task) for task in \
                        [getattr(self, csv_method)() for csv_method in method_names(removeprefix=False)]]
        
        all_dataframes = await asyncio.gather(*df_tasks)
        all_df_methods = ArgMapper({method: df for method,df in zip(method_names(), all_dataframes)})
        return all_df_methods
    
    def _get_methods(self, removeprefix=True) -> List[AnyStr]:
        '''Removes prefix names for all asynchronous DataFrame methods'''
        return [i if not removeprefix else i.removeprefix('process_') for i in dir(CSVProcessor) if re.match(r'^process', i) and asyncio.iscoroutinefunction(getattr(self, i))]
    
    @cached_property
    def dataframes(self) -> T:
        '''
        Returns ArgMapper: An instance containing dataframes.
        
        >>> Use attribute names to retrieve DataFrame objects (instances of pd.DataFrame).
        '''
        if CSVProcessor._dataframes is None:
            CSVProcessor._dataframes = asyncio.run(self.execute_all())
        return CSVProcessor._dataframes
    
    @property
    def export(self) -> str:
        ''' >>> Exports all DataFrames to CSV files'''
        df_methods = self._get_methods()
        (getattr(self.dataframes, df).to_csv(f'{self._path / df}.csv', index=False) for df in df_methods)
        print(f'\033[1;32mSuccessfully converted {len(self.dataframes)} JSON files to CSV format.\033[0m')

class NLTKLoader:
    _stopwords = None
    _nltk = None
    '''
    ### Note:
        >>> The NLTKLoader class is designed to provide a convenient way for accessing
            a unified set of NLTK stopwords from all languages to be used for Tensforflow text filtering.
    '''
    def __init__(self, __ext_path=None) -> None:
        '''
        ### Args:
        - __ext_path: A dummy argument mainly used for caching purposes.
            It represents the path to the NLTK stopwords data directory, but its value does not
            affect the functionality of the class. The class caches the stopwords, so this
            argument is provided for caching purposes.
        '''
        if __ext_path is None:
            __ext_path = Path.home() / 'nltk_data/corpora/stopwords'
        self.ext_path = __ext_path
    
    @cached_property
    def _filter_stopwords(self) -> List[str]:
        '''Filters all NLTK stopwords (for all languages) into a single frozenset
        
        The STOPWORDS property filters and combines NLTK stopwords from multiple languages into
        a single set then converted back into a list for Tensorflow purposes. It ensures efficient and consistent access to common stop words for
        natural language processing and text analysis.

        Note:
            >>> This property utilizes the NLTK library and its data, and it may perform an initial
            download of the stopwords data if not already present in the specified or default path.
        '''
        stopwords = [[word for word in words if word] \
                    for lang, words in self.nltk.items() \
                    if re.match(r'[a-z].*[a-z]$', lang)]
        cleaned_stopwords = OrderedDict.fromkeys(*[map(str.lower, chain.from_iterable(stopwords))])
        return list(cleaned_stopwords)
    
    @cached_property
    def stopwords(self) -> List[str]:
        if NLTKLoader._stopwords is None:
            nltk_stopwords = self._filter_stopwords
        NLTKLoader._stopwords = nltk_stopwords
        return NLTKLoader._stopwords

    @lru_cache(maxsize=None)
    def _nltk_files(self) -> ArgMapper:
        ssl._create_default_https_context = ssl._create_unverified_context
        download('stopwords', quiet=True, force=True, raise_on_error=True)
        return DataLoader(ext_path=self.ext_path).mapper
    
    @cached_property
    def nltk(self) -> ArgMapper[Dict]:
        if NLTKLoader._nltk is None:
            nltk_files = self._nltk_files()
        NLTKLoader._nltk = nltk_files
        return NLTKLoader._nltk

@lru_cache(maxsize=None)
def loader(*keys: Optional[AnyStr], mapper: bool=False) -> List[Union[ArgMapper, Dict, Exception]]:
    '''
    key -> folder name: Optional[str] = None (Loads all JSON files)
    This function is mainly for this projects data rather for external use.
    Otherwise use DataLoader (dl) ext_path argument if needed.
    (E.g dl(ext_path=Path.home() / 'nltk_data/corpora/stopwords')(mapper: bool=False))
    
    Returns ArgMapper instance of folder for given key name.
    
    E.g
    all_hadiths = loader('hadiths')
    all_hadiths.<file_name> or use regular dictionary `get` methods including brackets
    
    To return all folders at once (iterate through all valid paths):
    E.g
    {folder: loader(folder) for _,folder in enumerate(<all_folder_paths>)}
    '''
    _JSONS = Path('jsons')
    _EXCLUDE = re.compile(r'(?!quran)', flags=re.IGNORECASE)
    _FOLDERS = ['', *[i.name for i in (MAIN_DIR / _JSONS).glob('*') if i.is_dir() and _EXCLUDE.match(i.name)]]
    
    _error = lambda __key, __color=False: f'`{__key}` not found' if not __color \
                                        else f'\033[1;31m`{__key}` is invalid. No available contents.\033[0m'
    
    _folders: Dict[ArgMapper] = {_JSONS.as_posix() if not folder else folder: DataLoader(folder_path=_JSONS / folder).mapper
                                for folder in _FOLDERS}
    _arg: Dict[ArgMapper] = {_error(key) if key not in _folders else key: _folders.get(key, _error(key, True)) for key in keys}
    if not keys:
        #** Loads all folders by default if no key is provided (ArgMapper instance)
        if mapper:
            return ArgMapper({i: _folders[i] for i in _folders.keys()})
        return _folders #** Dict[ArgMapper] instance
    elif keys:
        if mapper: return ArgMapper(_arg)
        else: return _arg #** Dict[ArgMapper] instance
    else: return _error

#^ Filtered NLTK stopwords
STOPWORDS: List[str] = NLTKLoader().stopwords
#^ All structured JSON files (JSONs + folders[JSONs])
'''d
- Automatically includes future folders in the global scope.
- Global variables utilized for CSVProcessor.
- Objects are designated as constants, hence represented in uppercase.
'''
globals().update({__folder.upper(): __contents for __folder, __contents in loader(mapper=True).items()})

#^ All structured JSON files converted to DataFrames (CSVs)
CSVS: ArgMapper[pd.DataFrame] = CSVProcessor().dataframes

if __name__ == '__main__':
    pprint(STOPWORDS)
    # print(JSONS)
    # print(CSVS)
    pass










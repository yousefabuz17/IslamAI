import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path
from collections import OrderedDict
from functools import lru_cache
from dataclasses import dataclass

from typing import Union

@dataclass
class ArgMapper:
    _p_string = '\n[ATTRIBUTES FOR {}]\n{}'
    
    def __init__(self, dict_, dont_map=False, _p_key=None, paths=None):
        self._p_key = f'{_p_key} ({self.__class__.__name__} instance)'
        self._data_files = ((key, value) for key,value in dict_.items())
        if dont_map and paths:
            for path in paths:
                file_name = path.stem
                self._data_files[file_name] = path
        for key, value in dict_.items():
            setattr(self, key, value)
    
    def __str__(self):
        return self.__repr__()
    
    def __repr__(self):
        str_ = '''
        1. To Obtain contents of files, use the name of the file as the property name.
        2. If no file names are shown, use `get_files` property for all files (PosixPaths)
        '''
        lst = [i for i in dir(self) if not re.match(r'^\_[a-z]', i)]
        return f'{str_}\n{self._p_string.format(self._p_key, lst)}'
    
    @property
    def get_files(self):
        return self._data_files
    
    def get(self, key, default=None):
        try:
            return getattr(self, key)
        except AttributeError:
            return default

    def __getitem__(self, key):
        return self.get(key)

class DataLoader(ArgMapper):
    def __init__(self, folder_path='jsons', file_ext='json', ext_path=''):
        '''
        1. Use self.get_files if folder contains directories
        2. Use folder_path for islamic_data purposes (e.g 'jsons/quran/altafsir')
        '''
        self.ext_path = ext_path
        self.file_ext = file_ext
        self.path = Path(__file__).parent.parent.absolute() / 'islamic_data' / folder_path if not self.ext_path else Path(self.ext_path)
        self._data_files = self._get_all_files()

    def _get_all_files(self):
        return self.path.rglob(f'*.{self.file_ext}' if not all([self.ext_path, self.file_ext]) else '*')
    
    @property
    def get_files(self):
        return self._data_files
    
    def __str__(self):
        if isinstance(self, DataLoader):
            return self.__repr__()
        elif isinstance(self, ArgMapper):
            return super().__str__()
    
    def __repr__(self):
        str_ = '''Options to obtain file contents:
                    1. Turn DataLoader to ArgMapper -> 
                        i. pass argument `mapper` when calling loader (e.g DataLoader(dict_, **kwargs)(mapper=True))
                        ii. use .mapper property for conversion (e.g DataLoader(dict_, **kwargs).mapper)
                    2. Use `get_files` property for generator of files'''
        attributes = [i for i in dir(self) if not re.match(r'^\_[a-z]', i)] + [i.stem for i in self._get_all_files()]
        args = f'{self.path.stem} ({self.__class__.__name__} instance)', attributes
        return str_ + self._p_string.format(*args)
    
    @staticmethod
    def add(*args: dict, **kwargs):
        '''
            args: dict of all files loaded from DataLoader to be added with.
            kwargs: kwarg=key_name
            Ex:
                DataLoader.add(*args, key1='')
        '''
        all_folder_names = [str(i) for i in range(1, len(args)+1)] if not kwargs else tuple(kwargs.values())
        all_added_files = ArgMapper({folder_name: folder_files for folder_name, folder_files in zip(all_folder_names, args)})
        return all_added_files

    def load_data(self, file_path: Path):
        def json_map():
            try:
                with open(self.path / f'{file_name}.{self.file_ext}', mode='r', encoding='utf-8') as file:
                    data = json.load(file)
                return data
            except FileNotFoundError:
                raise FileNotFoundError(f"Data file not found at {file_name}")
            except json.JSONDecodeError as e:
                raise ValueError(f"Error decoding JSON in {file_name}: {e}")
        
        def ext_map():
            '''Mainly for files without any extension (e.g corpora/stopwords/*)'''
            try: return open(self.path / file_name, mode='r', encoding='utf-8').read().splitlines()
            except FileNotFoundError: raise FileNotFoundError(f"Data file not found at {file_name}")
        
        file_name = file_path.stem 
        data = json_map() if not self.ext_path else ext_map()
        return file_name, data

    def __call__(self, mapper: bool=False):
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
        contains_dirs = any([i.is_dir() for i in all_file_paths])
        if mapper and not contains_dirs:
            return ArgMapper(all_files, _p_key=self.path.stem)
        elif contains_dirs:
            return ArgMapper(all_files, _p_key=self.path.stem, dont_map=True, paths=all_file_paths)
        return self

    @staticmethod
    def load_file(path='', file_name='', ext='json', **kwargs):
        default_values = ('r', None)
        mode, encoding = tuple(kwargs.get(key, default_values[i]) for i,key in enumerate(('mode','encoding')))
        '''
        path='', file_name='', mode='r', encoding='utf-8', ext='json'
        Returns:
        - For JSON files: the loaded json file.
        - For PDF files: ommit mode when etx is PDf
        '''
        main_data_path = Path(__file__).parent.parent.absolute() / 'islamic_data'
        mode = 'rb' if ext=='pdf' else mode
        file_name = f'{file_name}.{ext}'
        file = open(main_data_path / path / file_name, mode=mode, encoding=encoding)
        if ext=='json':
            file = json.load(file)
        return file

    @property
    def mapper(self):
        return self(mapper=True)

    @classmethod
    @lru_cache(maxsize=1)
    def _translate_text(cls, *args):
        from transformers import MarianConfig, MarianMTModel, MarianTokenizer, pipeline
        text, src_lang, tgt_lang = args
        model_name = f'Helsinki-NLP/opus-mt-{src_lang}-{tgt_lang}'
        config = MarianConfig.from_pretrained(model_name, revision="main")
        model = MarianMTModel.from_pretrained(model_name, config=config)
        tokenizer = MarianTokenizer.from_pretrained(model_name, config=config)
        translation = pipeline("translation", model=model, tokenizer=tokenizer)
        translated_text = translation(text, max_length=512, return_text=True)[0]
        return translated_text.get('translation_text')

    @classmethod
    def translate(cls, *args):
        return cls._translate_text(*args)

@lru_cache(maxsize=1)
def loader(key='jsons'):
    '''
    This function is mainly for this projects data rather external.
    Use DataLoader (dl) ext_path argument if needed.
    (E.g dl(ext_path=f'{Path.home()}/nltk_data/corpora/stopwords)(mapper: bool=False))
    
    Returns ArgMapper instance of folder for given key name.
    
    E.g
    all_hadiths = loader(key='hadiths)
    all_hadiths.<file_name> or use regular dictionary `get` methods including brackets
    
    To return all folders at once (Temporary folder name can be changed to personal liking), simply do:
    {folder: loader(key=folder) for _,folder in enumerate(('jsons', 'hadiths', 'pillars', 'salah'))}
    '''
    global stopwords
    
    dl = DataLoader
    hadiths, pillars, salah = (dl(folder_path=f'jsons/{i}').mapper for _,i in enumerate(('hadiths', 'pillars', 'salah')))
    #^ All NLTK Stopwords
    stopwords = dl(ext_path=f'{Path.home()}/nltk_data/corpora/stopwords').mapper
    return dl().mapper if key=='jsons' else locals().get(key)

def main():
    return DataLoader(folder_path='jsons', file_ext='json').mapper

if __name__ == '__main__':
    main()

#** Initiates NLTK stopwords globally
loader()
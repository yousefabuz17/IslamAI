import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path
from collections import OrderedDict

class DataLoader:
    def __init__(self, folder_path='jsons', file_ext='json'):
        self.file_ext = file_ext
        self.path = Path(__file__).parent.parent.absolute() / 'islamic_data' / folder_path
        self.data_files = self.path.rglob(f'*.{file_ext}')

    @staticmethod
    def add(*args: dict, **kwargs):
        '''
            args: dict of all files loaded from DataLoader to be added with.
            kwargs: folder<int: 1>
        '''
        all_data = [i for i in args]
        all_folder_names = tuple(kwargs.get(f'folder{idx}') for idx,_ in enumerate(kwargs.items(), start=1))
        all_added_files = OrderedDict({folder_name: folder_files for folder_name, folder_files in zip(all_folder_names, all_data)})
        return all_added_files

    def load_data(self, file_path: Path):
        def _load_and_map():
            try:
                with open(self.path / f'{file_name}.{self.file_ext}', mode='r', encoding='utf-8') as file:
                    data = json.load(file)
                return data
            except FileNotFoundError:
                raise FileNotFoundError(f"Data file not found at {file_name}")
            except json.JSONDecodeError as e:
                raise ValueError(f"Error decoding JSON in {file_name}: {e}")
        
        file_name = file_path.stem 
        data = _load_and_map()
        return file_name, data

    def __call__(self):
        all_files = {}
        with ThreadPoolExecutor(max_workers=cpu_count() // 2) as executor:
            future_to_file = {executor.submit(self.load_data, file_path): file_path for file_path in self.data_files}

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    file_name, data = future.result()
                    all_files[file_name] = data
                except Exception:
                    ...
        return all_files

    @staticmethod
    def load_file(path='', file_name='', ext='json', **kwargs):
        default_values = ('r', 'utf-8')
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
    def get_files(self):
        return self.data_files

def main():
    return DataLoader(folder_path='jsons', file_ext='json')()
if __name__ == '__main__':
    main()
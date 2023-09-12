import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count
from pathlib import Path

class DataLoader:
    def __init__(self):
        self.path = Path(__file__).parent.parent.absolute() / 'islamic_data' / 'jsons'
        self.data_files = self.path.rglob('*.json')

    def load_data(self, file_path):
        def _load_and_map(file_name):
            try:
                with open(self.path / f'{file_name}.json',
                            mode='r', encoding='utf-8') as file:
                    data = json.load(file)
                return data
            except FileNotFoundError:
                raise FileNotFoundError(f"Data file not found at {file_name}")
            except json.JSONDecodeError as e:
                raise ValueError(f"Error decoding JSON in {file_name}: {e}")
        file_name = file_path.stem 
        data = _load_and_map(file_name)
        return file_name, data
    
    @property
    def get_files(self):
        return self.data_files

loader = DataLoader()
all_files = {}

with ThreadPoolExecutor(max_workers=cpu_count() // 2) as executor:
    future_to_file = {executor.submit(loader.load_data, file_path): file_path for file_path in loader.get_files}

    for future in as_completed(future_to_file):
        file_path = future_to_file[future]
        try:
            file_name, data = future.result()
            all_files[file_name] = data
        except Exception as e:
            print(f"Error loading data for {file_path}: {e}")

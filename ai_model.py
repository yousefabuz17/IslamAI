import re
from os import environ
import logging
logging.getLogger('tensorflow').setLevel(logging.ERROR)
environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
environ["KMP_AFFINITY"] = "noverbose"
from collections import OrderedDict
import tensorflow as tf
from tensorflow.keras.layers.experimental.preprocessing import TextVectorization # type: ignore
from nltk.sentiment import SentimentAnalyzer, SentimentIntensityAnalyzer
from nltk.sentiment.util import extract_unigram_feats, mark_negation
from nested_lookup import nested_lookup as nested
from blueprints.data_loader import (stopwords, loader, ArgMapper, DataLoader as dl)


load, translate = (getattr(dl, i) for _,i in enumerate(('load_file', 'translate')))
folder_names = ('jsons', 'hadiths', 'pillars', 'salah')
data = ArgMapper({folder: loader(key=folder) for _,folder in enumerate(folder_names)})

sentiment_analyzer, intensity_analyzer = SentimentAnalyzer(), SentimentIntensityAnalyzer()
feature_extractors = [extract_unigram_feats, mark_negation]

class TextProcessor:
    def __init__(self, text: str, **kwargs):
        self.kwargs = kwargs
        self.text = self._filter_stopwords(text)
        self._vectorizer = self._get_vector()
        self.vectorized_sequences = self._get_vect_sequences()
        self.polarity = self._get_polarity(text)

    def _get_vector(self):
        default_values = (100, None, 'int', 100, None)
        default_args = ('max_tokens', 'ngrams', 'output_mode', 'output_sequence_length')
        new_kwargs = {arg: self.kwargs.get(arg, value) for arg, value in zip(default_args, default_values)}
        return TextVectorization(**new_kwargs)
    
    @staticmethod
    def _filter_stopwords(text):
        text = text.split('-') if re.match(r'^\S*$', text) else text.split()
        stopwords_contents = [' '.join(getattr(stopwords, i)) for i in vars(stopwords).keys() if re.match(r'^[a-z].*[a-z]$', i)]
        flattened_stopwords = ' '.join([i.lower().strip() for i in stopwords_contents]).split()
        # compiler = re.compile('|'.join([re.escape(i) for i in flattened_stopwords]))
        return [i for i in text if i.lower() not in flattened_stopwords]

    def _get_vect_sequences(self):
        self._vectorizer.adapt(self.text)
        return self._vectorizer(self.text)
    
    def _get_polarity(self, text):
        return intensity_analyzer.polarity_scores(text)
    
    def get_config(self):
        return self._vectorizer.get_config()

    def get_vocabulary(self):
        vocabs = self._vectorizer.get_vocabulary()
        vocabs[0] = self.kwargs.get('oov_token', '[START]')
        return vocabs

    @property
    def word_index(self):
        return {word: index for word, index in zip(self.get_vocabulary(), range(0, len(self.get_vocabulary()) + 1))}

def process_text(text, **kwargs):
    return TextProcessor(text, **kwargs)

class QuranModel:
    '''
    ~ TextProcessing and Training for the Quran in all available languages.
    ~ Files: Altafsir & SurahQuran
    '''
    _altafsir = data.jsons['all-surahs-altafsir']
    _surahquran = data.jsons['all-surahs-surahquran']
    
    def __init__(self):
        self.altafsir = self._process_altafsir(self._altafsir)
        self.surahquran = self._process_surahquran(self._surahquran)
    
    def _process_altafsir(self, file):
        ...
    
    def _process_surahquran(self, file):
        all_surah_names = list(file.keys())
        all_lang_verses = OrderedDict({all_surah_names[idx]: {**lang_verses} for idx, lang_verses in enumerate(nested('verses', file))})
        all_contents = []
        return all_lang_verses['1-Al-Fatihah']['English']

test1 = load(path='jsons/quran/altafsir', file_name='1-Al-Fatihah')['text']
test2 = QuranModel().surahquran
lst = list(test2.values())[0]
# print(test2)
tf_tokenizer = process_text(lst, max_tokens=100)
#     a[idx].append(ArgMapper({key: getattr(tf_tokenizer, i) for _,i in enumerate(('vectorized_sequences', 'word_index', 'polarity', 'text'))}))
print(tf_tokenizer.vectorized_sequences)
print(tf_tokenizer.word_index)
print(tf_tokenizer.polarity)
print(tf_tokenizer.text)

# print([getattr(tf_tokenizer, i) for _,i in enumerate(('vectorized_sequences', 'word_index', 'polarity'))], sep='\n\n\n')


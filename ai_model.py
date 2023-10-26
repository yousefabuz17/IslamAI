import re
from os import environ
from functools import lru_cache
import logging
logging.getLogger('tensorflow').setLevel(logging.ERROR)
environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
environ["KMP_AFFINITY"] = "noverbose"
import tensorflow as tf
from tensorflow.keras import Sequential #type: ignore
from tensorflow.keras.layers import Embedding, Dense # type: ignore
from tensorflow.keras.layers.experimental.preprocessing import TextVectorization # type: ignore
from nltk.sentiment import SentimentIntensityAnalyzer
from blueprints.data_loader import (STOPWORDS, CSVS)
from pydantic import BaseModel, ValidationError


intensity_analyzer = SentimentIntensityAnalyzer()

class TextProcessor:
    class Validator(BaseModel):
        string: str
    
    def __init__(self, text, **kwargs):
        self.kwargs = kwargs
        self.text = self._filter_stopwords(text)
        self._vectorizer = self._get_vector()
        self.vectorized_sequences = self._get_vect_sequences()
        self.polarity = self._get_polarity(text)
    
    @staticmethod
    def _validate_str(t):
        try: return TextProcessor.Validator(string=t).string
        except ValidationError: return ''.join(t)
    
    def _get_vector(self):
        default_values = (100, None, 'int', 100, None)
        default_args = ('max_tokens', 'ngrams', 'output_mode', 'output_sequence_length')
        new_kwargs = {arg: self.kwargs.get(arg, value) for arg, value in zip(default_args, default_values)}
        return TextVectorization(**new_kwargs)
    
    @staticmethod
    def _filter_stopwords(text):
        org_text = TextProcessor._validate_str(t=text)
        fix_text = org_text.translate(str.maketrans('','','\t\n'))
        sep = '-' if re.match(r'^\S*$', org_text) else ' '
        updated_text = tf.strings.split([fix_text], sep=sep).numpy().tolist()[0]
        stopwords_contents = [getattr(STOPWORDS, i) for i in vars(STOPWORDS).keys() if re.match(r'^[a-z].*[a-z]$', i)]
        flattened_stopwords = tf.concat(stopwords_contents, axis=0)
        return [i for i in updated_text if tf.strings.lower(i) not in flattened_stopwords]

    def _get_vect_sequences(self):
        self._vectorizer.adapt(self.text)
        return tf.constant(self._vectorizer(self.text))
    
    @staticmethod
    def _get_polarity(text):
        return intensity_analyzer.polarity_scores(TextProcessor._validate_str(t=text))
    
    def get_config(self):
        return self._vectorizer.get_config()

    def get_vocabulary(self):
        vocabs = self._vectorizer.get_vocabulary()
        vocabs[1] = self.kwargs.get('oov_token', '[UNK]')
        return vocabs

    @property
    def word_index(self):
        return {word: index for word, index in zip(self.get_vocabulary(), range(0, len(self.get_vocabulary()) + 1))}
    
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
    
def process_text(text, **kwargs):
    return TextProcessor(text, **kwargs)

# test1 = load(path='jsons/quran/altafsir', file_name='1-Al-Fatihah')['text']
# lst = list(test2.values())[0]
# tf_tokenizer = process_text([test1[0]], max_tokens=100)
# embedding_dim = len(tf_tokenizer.vectorized_sequences.numpy()[0])
# embedding_layer = Sequential(Embedding(input_dim=len(tf_tokenizer.word_index)+1, output_dim=embedding_dim, sparse=True))

# embedded_sequences = embedding_layer(tf_tokenizer.vectorized_sequences)

# print(
#     f'''
#     Vectorized Sequence: {tf_tokenizer.vectorized_sequences}
    
#     Word-Index: {tf_tokenizer.word_index}
    
#     Polarity Scores: {tf_tokenizer.polarity}
    
#     Filtered Input: {tf_tokenizer.text}
    
#     Embedded Sequences: {embedded_sequences}
#     ''')

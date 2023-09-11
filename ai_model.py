# import os

# os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
# import rasa
# import tensorflow as tf
# from transformers import MarianConfig, MarianMTModel, MarianTokenizer, pipeline
# import gensim
# from gensim.models import Word2Vec
# from nltk.tokenize import word_tokenize

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
    pass
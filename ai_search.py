# from deepdiff import DeepSearch
# from pathlib import Path
# import json
# from pprint import pprint
# import re
# from nested_lookup import nested_lookup as nested, get_all_keys
from blueprints.data_loader import DataLoader


# load = DataLoader.load_file
# file = load(path='jsons', file_name='all-surah-meanings')
# a = nested('verse-count', file)
# print(sum(a))
# file1 = DataLoader(folder_path='jsons/quran/surah-quran')()
# file2 = DataLoader(folder_path='jsons/quran/altafsir')()
# pattern = re.compile(r'null')
# all_ = DataLoader.add(file1, file2, folder1='surah-quran', folder2='altafsir')
# a = nested('null', all_)
# # a = [i for i in a if i=='']
# pprint(a)
# results = DeepSearch(a, pattern, strict_checking=True, use_regexp=True,verbose_level=3)
# print(results.get('matched_values', {}).keys())
import json
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score

# Load and preprocess JSON data
load = DataLoader.load_file
data_file1 = load(path='jsons/quran/altafsir', file_name='1-Al-Fatihah')
data_file2 = load(path='jsons/quran/surah-quran', file_name='1-Al-Fatihah')
# Create a list of JSON data
data_list = [data_file1, data_file2]  # Add more files if needed

# Extract labels (positive/negative sentiment) based on your criteria
# For this example, let's assume positive sentiment if "Al-Fatihah" is mentioned, otherwise negative sentiment.
labels = ["positive" if "Al-Fatihah" in data["name_simple"] else "negative" for data in data_list]

# Extract text data
text_data = [data["short_text"] for data in data_list]

# Split data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(text_data, labels, test_size=0.2, random_state=42)

# Create TF-IDF vectorizer
tfidf_vectorizer = TfidfVectorizer(max_features=1000)  # Adjust max_features as needed

# Transform text data into TF-IDF features
X_train_tfidf = tfidf_vectorizer.fit_transform(X_train)
X_test_tfidf = tfidf_vectorizer.transform(X_test)

# Train a classifier (e.g., Naive Bayes)
classifier = MultinomialNB()
classifier.fit(X_train_tfidf, y_train)

# Make predictions on the test data
y_pred = classifier.predict(X_test_tfidf)

# Calculate accuracy
accuracy = accuracy_score(y_test, y_pred)
print(f"Accuracy: {accuracy * 100:.2f}%")

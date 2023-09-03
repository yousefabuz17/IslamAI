# IslamAI - Quran and Islamic Knowledge AI Chatbot
`IslamAI` is an AI chatbot project designed to provide accurate and reliable information about the Quran and Islamic teachings. Unlike general-purpose chatbots, IslamAI is focused solely on answering questions related to the Quran and the Islamic religion. It utilizes data from the Quran and other Islamic sources to provide accurate and insightful answers to user queries.

## Table of Contents
- [Features](#features)
- [Code Organization](#code-organization)
- [Data Collection](#data-collection)
- [Data Processing](#data-processing)
- [Model Training](#model-training)
- [Configuration](#configuration)
- [Requirements](#requirements)
- [Project Structure](#project-structure)
- [Progress](#progress)
- [Contributing](#contributing)
    - [Ali Zahid Raja's Links](#ali-zahid-rajas-links)


## Features
- `Quranic Information`: IslamAI is equipped with an extensive database of Quranic information. It can provide details about individual surahs, ayahs, and keywords within the Quran.

- `Islamic Teachings`: The chatbot can answer questions about various aspects of Islamic teachings, rituals, and practices based on reliable sources.

- `Interactive Interface`: Users can interact with IslamAI by asking questions and receiving informative responses.


## **Code Organization**

- **``Modular Approach``**: The code is meticulously organized into modular components, following best practices in software design. Each major feature, such as *QuranAPI*, *HadithAPI*, and *IslamFacts*, is encapsulated in a separate class. This modular structure ensures that future changes or additions can be made with ease, as each component is self-contained and independent.

- **``Configurability``**: Configuration settings are thoughtfully separated from the code, allowing for straightforward adjustments and customization without the need to modify the core logic. This separation of concerns simplifies maintenance and ensures that future changes to configuration parameters are hassle-free.

- **``Singleton Pattern``**: The Singleton pattern is applied strategically to guarantee that only one instance of specific classes, like *QuranAPI*, is created. This design choice optimizes resource utilization and simplifies future updates or extensions.

- **``AsyncIO``**: Asynchronous programming with *asyncio* is employed to facilitate efficient concurrent operations. This approach enhances performance and responsiveness, making it straightforward to incorporate additional asynchronous tasks or enhancements in the future.

- **``Data Serialization``**: JSON files are chosen as the data storage and retrieval format. This decision enhances data integrity and portability. Should there be a need to change data storage formats or structures, the transition process remains straightforward.

- **``Code Efficiency``**: The use of caching mechanisms, like LRU caching, optimizes performance and resource utilization.

- **``Libraries and Frameworks``**: The choice of libraries and frameworks ensures that the codebase remains compatible with the latest developments in these technologies, making future updates and maintenance seamless. Here are some of the libraries and frameworks used in this project:

| Library/Framework | Description |
|-------------------|-------------|
| `TensorFlow`        | TensorFlow is a widely adopted machine learning framework that powers the AI capabilities of this project. |
| `Transformers`      | The Transformers library, known for its natural language processing capabilities, plays a key role in enhancing the chatbot's language understanding. |
| `aiohttp`           | aiohttp is used for asynchronous HTTP requests, optimizing performance and responsiveness. |
| `bs4 (BeautifulSoup)`     | BeautifulSoup aids in web scraping and data extraction, ensuring accurate and up-to-date information. |
| `concurrent.futures (ThreadPoolExtractor)`    | Provides a high-level interface for asynchronously executing functions.       |

## **Data Collection**

- **``Structured Data``**: The project excels in collecting and structuring data from various sources. This structured data is easily accessible, facilitating accurate responses to user queries. If the data sources or structures evolve over time, adapting the code to accommodate these changes is straightforward, thanks to the meticulous data handling approach.

- **``Parallel Processing``**: Parallel processing techniques are employed skillfully to efficiently extract and process large datasets, such as Quranic content and Hadiths. This design decision ensures that the project can scale to handle even larger datasets in the future, without major code overhauls.

- **``Data Integrity``**: The project is designed to ensure data integrity. For example, the Quranic content is extracted from multiple sources and cross-checked to ensure accuracy and consistency. This approach guarantees that the chatbot provides reliable and trustworthy information.

- **``Data Storage``**: The project uses JSON files to store data. This choice enhances data integrity and portability. Should there be a need to change data storage formats or structures, the transition process remains straightforward.

## **Data Processing**

- **``Data Preprocessing``**: The project employs a variety of data preprocessing techniques to ensure that the data is clean and ready for use. For example, the Quranic content is preprocessed to remove unnecessary characters and whitespace. This approach guarantees that the chatbot provides accurate and reliable information.


## **Model Training**
- **``Conversational AI with Rasa``**: The model training process utilizes Rasa, an open-source conversational AI framework. Rasa enables the creation of a powerful AI model from scratch, capable of understanding user queries and generating context-aware responses tailored to Quranic and Islamic knowledge.

- **``NOTE``**: Data collection still in progress. Model training will be done after majority of data is successfully collected and structured

## Configuration

```ini
[Database]
quran_host = al-quran1.p.rapidapi.com
quran_url = https://al-quran1.p.rapidapi.com
quran_api = <rapidapi key>
hadith_url = https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions.min.json
islam_facts = https://fungenerators.com/random/facts/religion/islam
myislam = https://myislam.org
allah_names = https://99namesofallah.name/
translate_api = <huggingface api>
aladhan = http://api.aladhan.com/v1
```

## Requirements

```bash
pip install -r requirements.txt
```

## Project Structure

```bash
IslamAI
├── islamic_data
│   ├── htmls
│   │   ├── *.html
│   ├── jsons
│   │   ├── *.json
│   ├── pdfs
│   │   ├── *.pdf
│   └── SOURCES.md
├── ai_data.py
├── ai_model.py
├── config.ini
├── README.md
└── requirements.txt
```

## Progress
- [ ] Data Collection
    - [ ] Data Processing
- [ ] Model Training
- [ ] Model Deployment
- [ ] ChatBot Interface
- [ ] Testing
- [ ] Deployment

## Contributing
- There is another project, much similar to IslamAI, that shares my passion for advancing Islamic knowledge through AI technology. The founder, **``Ali``**, maintains an active Discord channel where contributors collaborate, share ideas, and support each other's initiatives. This collaborative spirit allows us to collectively improve AI-driven Islamic knowledge platforms for the benefit of users worldwide.

- Feel free to join Ali Zahid Raja's Discord channel to participate in this collaborative effort and contribute to the development of cutting-edge solutions for Islamic education and information dissemination. Together, we can make a substantial impact on the way people access and learn about Islam.
---

### **Ali Zahid Raja's Links**

| Platform | Link                                         |
|----------|----------------------------------------------|
| Website  | [Portfolio](https://alizahidraja.com/) |
| Discord  | [Islam & AI](https://discord.gg/HhGaJan3Xj) |
| GitHub   | [QURAN-NLP](https://github.com/islamAndAi/QURAN-NLP) |
| Project   | [IslamAndAI](https://islamandai.com/) |


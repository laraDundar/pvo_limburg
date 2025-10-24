# PVO_Limburg 

# Project Prototype Overview
>> For the prototype we have a Streamlit-based dashboard for analyzing and visualizing news articles scraped from various sources.

>> The sources we currently have are: NCSC, de Limburger, NOS.nl and security.nl 

>> This prototype provides:

>> webScrapers --> Under these folders there are .py files used to scrape RSS feeds and historical website data.

>> scrapedArticles --> The folder with resulting .json files that have all the articles.

>> merge_jsons --> Concates all the .json files under the scrapedArticles folder and creates all_articles.json for pre_process.py to use.

>> geo_filter.py and sme_filter.py are the files containing all the methods that do the article filtering inside the pre_process.py file don't run them by themselves.

>> pre_process.py --> This is the main file. If you run this you can see the filtered articles and the coverage of the labeling functions for debugging. It produces the files under the keywords folder. If you want to run the dashboard, you don't have to run the pre_process.py file, if you add new articles to all_articles then you need to run it to update the keywords folder.

>> to run dashboard.py --> Use streamlit run dashboard.py
>> python -m streamlit run dashboard.py --> If the previous command doesn't work.
>> to stop running the dashboard just do ctrl + c.

# Setup Instructions 
>> pip install -r requirements.txt

>> run this in the terminal(if you are getting UnauthorizedAccess error): Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

>> Then activate your environment with: C:\Users etc. from your laptop setup\.venv\Scripts\Activate.ps1

# What We Have Learned
Through this prototype, we learned how to transform unstructured information into meaningful insights that can support decision-making for SMEs and organizations such as PVO Limburg. We gained hands-on experience with the full data pipeline — from data collection and integration (web scraping and merging external data sources) to text preprocessing and cleaning for analysis.

We explored multiple natural language processing (NLP) techniques, including TF-IDF, weak supervision and named entity recognition, and trend detection, to identify emerging themes related to crime, safety, and entrepreneurship in Netherlands and regions around. This helped us understand how AI can be applied to detect patterns and anomalies across diverse text sources such as news articles, police reports, and newsletters.

In addition, we learned to design interactive dashboards using Streamlit for data visualization, allowing users to explore and interpret trends at both operational and strategic levels.

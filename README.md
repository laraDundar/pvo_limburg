# PVO_Limburg 
# Before trying to run the code do these for setup:
# pip install -r requirements.txt
# run this in the terminal(if you are getting UnauthorizedAccess error): Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# Then activate your environment with: C:\Users etc. from your laptop setup\.venv\Scripts\Activate.ps1
# Run the pre_process.py file to create the keywords files.
# If you scrape more website add the .json file in the scrapedArticles folder, and run the merge_jsons.py to have one json file with all articles in it the it will be ready for pre_process.py to use.
# to run dashboard:
>> streamlit run dashboard.py
# python -m streamlit run dashboard.py --> This is only for me bc my laptop has mental problems...
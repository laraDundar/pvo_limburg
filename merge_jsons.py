import os
import json
import glob

# -------- CONFIGURATION --------
INPUT_DIR = "scrapedArticles"       # folder wherescraped JSON files are stored
OUTPUT_FILE = "all_articles.json"  # name of the merged output file
# --------------------------------

def merge_json_files(input_dir: str, output_file: str):
    all_articles = []
    seen_urls = set()

    json_files = glob.glob(os.path.join(input_dir, "*.json"))
    print(f"🔍 Found {len(json_files)} JSON files in '{input_dir}'")

    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data = [data]
                elif not isinstance(data, list):
                    continue  # skip malformed entries

                for item in data:
                    url = item.get("url")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_articles.append(item)
        except Exception as e:
            print(f"⚠️ Skipping {file_path}: {e}")

    print(f"✅ Merged {len(all_articles)} unique articles from {len(json_files)} files.")

    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(all_articles, out, ensure_ascii=False, indent=2)

    print(f"💾 Saved merged file to: {output_file}")

if __name__ == "__main__":
    merge_json_files(INPUT_DIR, OUTPUT_FILE)

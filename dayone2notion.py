import json
import glob
import os
import pandas as pd

def process_dayone_json(json_dir, output_csv):
    """
    Reads all JSON files in the specified directory and converts DayOne entries to a CSV file.

    Args:
        json_dir (str): Directory containing DayOne JSON files.
        output_csv (str): Path to the output CSV file.
    """
    all_entries = []

    # Find all JSON files in the directory
    json_files = glob.glob(os.path.join(json_dir, "*.json"))

    print(f"Found {len(json_files)} JSON files in {json_dir}")

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

                if 'entries' not in data:
                    print(f"Skipping {file_path}: No 'entries' key found.")
                    continue

                for entry in data['entries']:
                    creation_date = entry.get('creationDate', '')
                    text = entry.get('text', '')

                    # Process photos
                    photos = []
                    if 'photos' in entry:
                        for photo in entry['photos']:
                            md5 = photo.get('md5')
                            file_type = photo.get('type')
                            if md5 and file_type:
                                filename = f"{md5}.{file_type}"
                                photos.append(filename)

                    photos_str = ", ".join(photos)

                    all_entries.append({
                        'Date': creation_date,
                        'Text': text,
                        'Photos': photos_str
                    })
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    # Create DataFrame and save to CSV
    if all_entries:
        df = pd.DataFrame(all_entries)
        # Notion prefers "Name" or similar for the title prop, but let's stick to the requested columns for now.
        # Often "Date" is auto-detected.

        df.to_csv(output_csv, index=False, encoding='utf-8')
        print(f"Successfully converted {len(all_entries)} entries to {output_csv}")
    else:
        print("No entries found.")

if __name__ == "__main__":
    # Assuming the script is run from the project root
    DAYONE_DIR = "dayone"
    OUTPUT_FILE = "dayone_export.csv"

    process_dayone_json(DAYONE_DIR, OUTPUT_FILE)

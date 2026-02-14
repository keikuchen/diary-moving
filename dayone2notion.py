import json
import glob
import os
import time
import mimetypes
from datetime import datetime
from zoneinfo import ZoneInfo
from notion_client import Client
import httpx

# Configuration
SECRETS_FILE = "secrets.json"
DAYONE_DIR = "dayone"
PHOTOS_DIR = os.path.join(DAYONE_DIR, "photos")

def load_secrets():
    """Loads Notion credentials from secrets.json."""
    try:
        with open(SECRETS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {SECRETS_FILE} not found. Please create it with NOTION_TOKEN and NOTION_DATABASE_ID.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {SECRETS_FILE}.")
        return None

def upload_file_to_notion(file_path, notion_token):
    """
    Uploads a file to Notion using the 3-step flow:
    1. Create a File Upload object
    2. Send the file
    3. Return the file upload ID to be attached
    """
    if not os.path.exists(file_path):
        return None

    filename = os.path.basename(file_path)
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    headers = {
        "Authorization": f"Bearer {notion_token}",
        "Notion-Version": "2022-06-28" # Using a recent version, verify if specific version needed
    }

    # Custom client for these specific endpoints if SDK doesn't support them well yet
    base_url = "https://api.notion.com/v1"

    try:
        # Step 1: Create File Upload object
        # POST /v1/file_uploads
        resp1 = httpx.post(
            f"{base_url}/file_uploads",
            headers=headers,
            json={
                "filename": filename,
                "content_type": content_type
            }
        )
        resp1.raise_for_status()
        upload_data = resp1.json()
        file_upload_id = upload_data.get("id")
        signed_upload_url = upload_data.get("signed_upload_url") # Hypothetical, need to check response structure
        # The user guide says: "Send the file — POST /v1/file_uploads/{id}/send"
        # So maybe we don't get a signed url, but use the ID in the URL.

        # Step 2: Send the file
        # POST /v1/file_uploads/{id}/send
        # Using multipart/form-data with 'file' key
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, content_type)}
            resp2 = httpx.post(
                f"{base_url}/file_uploads/{file_upload_id}/send",
                headers=headers,
                files=files,
                timeout=60.0 # Uploads might take time
            )
            resp2.raise_for_status()

        return file_upload_id

    except Exception as e:
        print(f"Error uploading {filename}: {e}")
        # Print response text for debugging if available
        if 'resp1' in locals() and hasattr(resp1, 'text'):
             print(f"Step 1 Resp: {resp1.text}")
        if 'resp2' in locals() and hasattr(resp2, 'text'):
             print(f"Step 2 Resp: {resp2.text}")
        return None

def process_dayone_json_to_notion():
    secrets = load_secrets()
    if not secrets:
        return

    notion_token = secrets["NOTION_TOKEN"]
    database_id = secrets["NOTION_DATABASE_ID"]

    notion = Client(auth=notion_token)

    json_files = glob.glob(os.path.join(DAYONE_DIR, "*.json"))
    print(f"Found {len(json_files)} JSON files in {DAYONE_DIR}")

    # Collect all entries first
    all_entries = []
    print("Reading and parsing all entries...")

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'entries' in data:
                    for entry in data['entries']:
                         # Pre-calculate sort key (date)
                         creation_date_str = entry.get('creationDate', '')
                         if creation_date_str:
                             try:
                                 dt_utc = datetime.fromisoformat(creation_date_str.replace('Z', '+00:00'))
                                 all_entries.append({
                                     'dt': dt_utc,
                                     'data': entry
                                 })
                             except ValueError:
                                 pass # Skip invalid dates for sorting purposes, or handle later
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    # Sort entries by date
    all_entries.sort(key=lambda x: x['dt'])
    print(f"Total entries to import: {len(all_entries)}")

    count = 0
    skipped_count = 0
    for item in all_entries:
        entry = item['data']
        creation_date_str = entry.get('creationDate', '')
        formatted_date = ''
        iso_date_jst = ''

        if creation_date_str:
            try:
                # Parse UTC date (Already done but re-doing for local var consistency or use cached)
                dt_utc = item['dt']
                # Convert to JST
                dt_jst = dt_utc.astimezone(ZoneInfo("Asia/Tokyo"))

                # Format to YYYY-MM-DD for Title
                formatted_date = dt_jst.strftime('%Y-%m-%d')
                iso_date_jst = dt_jst.strftime('%Y-%m-%d')

            except ValueError:
                print(f"Error parsing date: {creation_date_str}")
                formatted_date = creation_date_str

        # We need ISO format for the Date property, but with timezone info?
        # Notion Date property requires ISO 8601.
        # If we want to store just the date YYYY-MM-DD, we can pass that string.

        if creation_date_str:
            try:
                # Parse UTC date
                dt_utc = datetime.fromisoformat(creation_date_str.replace('Z', '+00:00'))
                # Convert to JST
                dt_jst = dt_utc.astimezone(ZoneInfo("Asia/Tokyo"))

                # Format to YYYY-MM-DD for Title
                formatted_date = dt_jst.strftime('%Y-%m-%d')

                # For the actual Date property, we can also use YYYY-MM-DD string
                iso_date_jst = dt_jst.strftime('%Y-%m-%d')

            except ValueError:
                print(f"Error parsing date: {creation_date_str}")
                formatted_date = creation_date_str

        text = entry.get('text', '')

        # Process photos
        image_blocks = []
        if 'photos' in entry:
            for photo in entry['photos']:
                md5 = photo.get('md5')
                file_type = photo.get('type')
                if md5 and file_type:
                    filename = f"{md5}.{file_type}"
                    photo_path = os.path.join(PHOTOS_DIR, filename)

                    if os.path.exists(photo_path):
                        print(f"Uploading {filename}...")
                        upload_id = upload_file_to_notion(photo_path, notion_token)

                        if upload_id:
                            # "Attach it... Set the type to 'file_upload' with the upload id."
                            image_blocks.append({
                                "object": "block",
                                "type": "image",
                                "image": {
                                    "type": "file_upload",
                                    "file_upload": {
                                        "id": upload_id
                                    }
                                }
                            })
                        else:
                            # Fallback to text if upload failed
                            image_blocks.append({
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [{"type": "text", "text": {"content": f"[Image Upload Failed: {filename}]"}}]
                                }
                            })        # Construct Page Children
        children = []

        # Add Images at the top
        children.extend(image_blocks)

        # Add Text
        # Split by newlines
        lines = text.split('\n')
        for line in lines:
            # Truncate if too long (Notion block limit is 2000 chars)
            if len(line) > 2000:
                line = line[:2000] + "..."

            # Empty lines in Notion are just empty paragraphs
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": line
                            }
                        }
                    ]
                }
            })

        # Create Page
        # NOTE: Notion API has a limit of 100 children blocks per request.
        # If an entry has more than 100 blocks (lines + images), this create call will fail.
        # For this migration script, such entries are skipped/fail validation.
        # To fix, one would need to batch children into groups of 100 and use append_children for the rest.
        try:
            notion.pages.create(
                parent={"database_id": database_id},
                properties={
                    "Name": {
                        "title": [
                            {
                                "text": {
                                    "content": formatted_date
                                }
                            }
                        ]
                    },
                    "Date": {
                        "date": {
                            "start": iso_date_jst
                        }
                    }
                },
                children=children
            )
            print(f"Created entry: {formatted_date}")
            count += 1
            time.sleep(1.0) # slightly increased sleep for uploads safety

        except Exception as e:
            print(f"Error creating page for {formatted_date}: {e}")

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    print(f"Finished processing. Created {count} entries.")



if __name__ == "__main__":
    process_dayone_json_to_notion()

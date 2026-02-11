import json
import os
import uuid
from datetime import datetime, timedelta, timezone


def convert_google_keep_to_day_one(keep_folder_path, day_one_json_file):
    day_one_entries = []

    for filename in os.listdir(keep_folder_path):
        if filename.endswith(".json"):
            with open(
                os.path.join(keep_folder_path, filename), "r", encoding="utf-8"
            ) as keep_file:
                note = json.load(keep_file)

            title = note.get("title", "")
            content = note.get("textContent", "")

            utc = timezone(timedelta(hours=0), "UTC")
            created_time = note.get("createdTimestampUsec", "")
            if created_time:
                created_time = datetime.fromtimestamp(
                    created_time / 1000000, utc
                ).isoformat()

            modified_time = note.get("userEditedTimestampUsec", "")
            if modified_time:
                modified_time = datetime.fromtimestamp(
                    modified_time / 1000000, utc
                ).isoformat()

            labels = note.get("labels", [])
            label_names = [label.get("name") for label in labels]

            day_one_entry = {
                # 小数点, ミリ秒6桁, タイムゾーン表記6文字(+00:00)を消し、Zを付与
                "creationDate": f"{created_time[:-13]}Z",
                "modifiedDate": f"{modified_time[:-13]}Z",
                "uuid": uuid.uuid4().hex.upper(),
                "text": f"{title}\n{content}",
                "tags": label_names,
                "starred": False,
                "duration": 0,
                "isAllDay": False,
                "isPinned": False,
                "editingTime": 0,
                "timeZone": "Asia/Tokyo",
            }
            day_one_entries.append(day_one_entry)

    entries_data = {"metadata": {"version": "1.0"}, "entries": day_one_entries}

    with open(day_one_json_file, "w", encoding="utf-8") as day_one_file:
        json.dump(entries_data, day_one_file, ensure_ascii=False, indent=4)

    print("Conversion completed successfully.")


# input(Google Keepからexportしたjsonファイル群が入ったディレクトリ)のパス
keep_folder_path = "keep_entries_folder"
# output(Day Oneにインポートするjsonファイル)のパス
day_one_json_file = "toBeImported.json"

# Google KeepからDay Oneに変換
convert_google_keep_to_day_one(keep_folder_path, day_one_json_file)

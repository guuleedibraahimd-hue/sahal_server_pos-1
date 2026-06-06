import json

with open("dhibic-dahab-online-store-firebase-adminsdk-fbsvc-70a4ef183a.json") as f:
    data = json.load(f)

result = json.dumps(data)

with open("output_key.txt", "w") as out:
    out.write(result)

print("DONE! output_key.txt ku eeg")
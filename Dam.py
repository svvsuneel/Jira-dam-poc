from flask import Flask, request, jsonify
import requests
from requests.auth import HTTPBasicAuth
import base64
import os
import threading

app = Flask(__name__)

print("ENV KEYS AT START:", list(os.environ.keys()))
# Jira config
JIRA_URL = "https://valuelabs2.atlassian.net"
EMAIL = "venkata.sanku@valuelabs.com"
API_TOKEN = os.environ.get("JIRA_API_TOKEN")   # ⚠️ regenerate token (security risk)

# Cloudinary config
CLOUD_NAME = "dthbqhoqk"
UPLOAD_PRESET = "Dam-poc"  # make sure this exists


# ----------------------------
# FILE TYPE DETECTION
# ----------------------------
def get_upload_type(file_name):
    image_ext = ["jpg", "jpeg", "png", "gif", "bmp", "webp"]

    ext = file_name.split(".")[-1].lower()

    if ext in image_ext:
        return "image"
    else:
        return "raw"


# ----------------------------
# DOWNLOAD ATTACHMENT
# ----------------------------
def download_attachment(attachment):
    try:
        attachment_id = attachment["id"]
        file_name = attachment["filename"]

        print(f"📥 Downloading: {file_name}")

        meta_url = f"{JIRA_URL}/rest/api/3/attachment/{attachment_id}"

        meta_response = requests.get(
            meta_url,
            auth=HTTPBasicAuth(EMAIL, API_TOKEN)
        )

        if meta_response.status_code != 200:
            print("❌ Metadata failed:", meta_response.text)
            return None, None

        content_url = meta_response.json().get("content")

        file_response = requests.get(
            content_url,
            auth=HTTPBasicAuth(EMAIL, API_TOKEN)
        )

        if file_response.status_code == 200:
            return file_response.content, file_name
        else:
            print("❌ Download failed:", file_response.text)
            return None, None

    except Exception as e:
        print("❌ Download error:", str(e))
        return None, None


# ----------------------------
# UPLOAD TO CLOUDINARY
# ----------------------------
def upload_to_cloudinary(file_bytes, file_name):
    try:
        upload_type = get_upload_type(file_name)

        upload_url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/{upload_type}/upload"

        files = {
            "file": (file_name, file_bytes)
        }

        data = {
            "upload_preset": UPLOAD_PRESET
        }

        response = requests.post(upload_url, files=files, data=data)

        print(f"☁️ Uploading {file_name} → {upload_type}")
        print("Status:", response.status_code)

        if response.status_code == 200:
            url = response.json().get("secure_url")
            print("✅ Uploaded:", url)
            return url
        else:
            print("❌ Upload failed:", response.text)
            return None

    except Exception as e:
        print("❌ Upload error:", str(e))
        return None


# ----------------------------
# PROCESS ALL ATTACHMENTS
# ----------------------------
def process_request(data):
    try:
        print("🚀 Processing webhook...")

        attachments = data.get("attachments", [])

        if not attachments:
            print("❌ No attachments received")
            return

        uploaded_urls = []

        for attachment in attachments:
            file_bytes, file_name = download_attachment(attachment)

            if not file_bytes:
                continue

            url = upload_to_cloudinary(file_bytes, file_name)

            if url:
                uploaded_urls.append({
                    "file": file_name,
                    "url": url
                })

        print("\n🎉 FINAL RESULT:")
        for item in uploaded_urls:
            print(f"{item['file']} → {item['url']}")

    except Exception as e:
        print("❌ Processing error:", str(e))


# ----------------------------
# WEBHOOK
# ----------------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        print("🔥 WEBHOOK HIT")

        data = request.get_json(force=True, silent=True)
        print("📦 Payload:", data)

        if not data:
            return jsonify({"status": "no data"}), 200

        threading.Thread(target=process_request, args=(data,)).start()

        return jsonify({"status": "accepted"}), 200

    except Exception as e:
        print("❌ Webhook error:", str(e))
        return jsonify({"error": str(e)}), 200


# ----------------------------
# START SERVER
# ----------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

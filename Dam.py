from flask import Flask, request, jsonify
import requests
from requests.auth import HTTPBasicAuth
import base64
import os
import threading

app = Flask(__name__)

print("ENV KEYS AT START:", list(os.environ.keys()))
# Jira config
JIRA_URL = "https://securonix.atlassian.net"
EMAIL = "vsuneel@securonix.com"
API_TOKEN = os.environ.get("JIRA_API_TOKEN")   # ⚠️ regenerate token (security risk)

# Cloudinary config
CLOUD_NAME = "dthbqhoqk"
UPLOAD_PRESET = "Dam-poc"  # make sure this exists


# ----------------------------
# TEST ENDPOINT
# ----------------------------
@app.route('/test', methods=['GET'])
def test():
    return "DAM Service Running ✅"


# ----------------------------
# STEP 1: Download Attachment from Jira
# ----------------------------
def download_attachment(attachment_url):
    print("📥 Downloading attachment...")

    try:
        # Extract attachment ID
        attachment_id = attachment_url.split("/")[-1]

        # Step 1: Get metadata
        meta_url = f"{JIRA_URL}/rest/api/3/attachment/{attachment_id}"

        meta_response = requests.get(
            meta_url,
            auth=HTTPBasicAuth(EMAIL, API_TOKEN)
        )

        print("Metadata status:", meta_response.status_code)

        if meta_response.status_code != 200:
            print("❌ Metadata fetch failed:", meta_response.text)
            return None

        content_url = meta_response.json().get("content")
        print("Media URL:", content_url)

        # Step 2: Download file
        file_response = requests.get(
            content_url,
            auth=HTTPBasicAuth(EMAIL, API_TOKEN)
        )

        print("Download status:", file_response.status_code)

        if file_response.status_code == 200:
            print("File size:", len(file_response.content))
            return file_response.content
        else:
            print("❌ Download failed:", file_response.text)
            return None

    except Exception as e:
        print("❌ Download exception:", str(e))
        return None


# ----------------------------
# STEP 2: Upload to Cloudinary
# ----------------------------
def upload_to_cloudinary(file_bytes, file_name="upload.jpg"):
    print("☁️ Uploading to Cloudinary...")

    try:
        upload_url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"

        files = {
            "file": (file_name, file_bytes)
        }

        data = {
            "upload_preset": UPLOAD_PRESET
        }

        response = requests.post(upload_url, files=files, data=data)

        print("Cloudinary status:", response.status_code)
        print("Cloudinary response:", response.text)

        if response.status_code == 200:
            secure_url = response.json().get("secure_url")
            print("✅ Uploaded URL:", secure_url)
            return secure_url
        else:
            return None

    except Exception as e:
        print("❌ Upload exception:", str(e))
        return None


# ----------------------------
# BACKGROUND PROCESS
# ----------------------------
def process_request(data):
    try:
        print("🚀 Processing request:", data)

        attachment_url = data.get("attachmentUrl")
        file_name = data.get("fileName", "file.jpg")

        if not attachment_url:
            print("❌ No attachment URL")
            return

        # Step 1: Download
        file_bytes = download_attachment(attachment_url)

        if not file_bytes:
            print("❌ Download failed")
            return

        # Step 2: Upload
        image_url = upload_to_cloudinary(file_bytes, file_name)

        if not image_url:
            print("❌ Upload failed")
            return

        print("🎉 SUCCESS: File uploaded to Cloudinary")
        print("URL:", image_url)

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

        # Run async
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

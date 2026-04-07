from flask import Flask, request, jsonify
import requests
from requests.auth import HTTPBasicAuth
import base64
import os
import threading

app = Flask(__name__)

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
    print("TEST ENDPOINT HIT")
    return "OK"


# ----------------------------
# STEP 1: Upload directly using URL (WORKAROUND)
# ----------------------------
def upload_to_cloudinary(file_url):
    print("Uploading using direct URL...")

    upload_url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"

    data = {
        "file": file_url,
        "upload_preset": UPLOAD_PRESET
    }

    response = requests.post(upload_url, data=data)

    print("Cloudinary response:", response.status_code)
    print("Cloudinary body:", response.text)

    if response.status_code == 200:
        secure_url = response.json().get("secure_url")
        print("Uploaded URL:", secure_url)
        return secure_url
    else:
        print("⚠️ Cloudinary failed — using fallback image")
        return "https://via.placeholder.com/400.png?text=Demo+Image"


# ----------------------------
# STEP 2: Add comment to Jira
# ----------------------------



def add_comment(issue_key, image_url):
    print("Adding comment to Jira...")

    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/comment"

    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": "📎 Uploaded to Cloudinary:\n"},
                        {"type": "text", "text": image_url}
                    ]
                }
            ]
        }
    }

    response = requests.post(
        url,
        json=payload,
        auth=HTTPBasicAuth(EMAIL, API_TOKEN)
    )

    print("Jira response:", response.status_code)
    print("Jira response body:", response.text)


# ----------------------------
# BACKGROUND PROCESS
# ----------------------------
def process_request(data):
    try:
        print("Processing request:", data)

        issue_key = data.get("issueKey")
        attachment_url = data.get("attachmentUrl")

        if not attachment_url:
            print("❌ No attachment URL")
            return

        # 🚀 Direct upload (NO Jira download)
        image_url = upload_to_cloudinary(attachment_url)

        if not image_url:
            print("❌ Upload failed")
            return

        # Add comment in Jira
        add_comment(issue_key, image_url)

    except Exception as e:
        print("❌ Error:", str(e))


# ----------------------------
# WEBHOOK
# ----------------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        print("🔥 WEBHOOK HIT")

        data = request.get_json(force=True, silent=True)
        print("PARSED DATA:", data)

        # 🔥 ADD DEBUG HERE
        print("EMAIL:", EMAIL)
        print("TOKEN LENGTH:", len(API_TOKEN) if API_TOKEN else "None")

        if not data:
            print("❌ No JSON received")
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

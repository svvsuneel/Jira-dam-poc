from flask import Flask, request, jsonify
import requests
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
# STEP 1: Download attachment
# ----------------------------
import base64

def download_attachment(url):
    print("Downloading attachment from Jira...")

    # Fix API version (important)
    url = url.replace("/rest/api/2/", "/rest/api/3/")

    # Create Basic Auth header manually
    auth_str = f"{EMAIL}:{API_TOKEN}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Accept": "*/*"
    }

    # Allow redirects (VERY IMPORTANT)
    response = requests.get(url, headers=headers, allow_redirects=True)

    print("Download status:", response.status_code)

    if response.status_code == 200:
        file_bytes = response.content
        print("File size:", len(file_bytes))
        return file_bytes
    else:
        print("Download failed:", response.text)
        return None

# ----------------------------
# STEP 2: Upload to Cloudinary
# ----------------------------
def upload_to_cloudinary(file_bytes):
    print("Uploading to Cloudinary...")

    upload_url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"

    files = {
        "file": ("upload.jpg", file_bytes)
    }

    data = {
        "upload_preset": UPLOAD_PRESET
    }

    response = requests.post(upload_url, files=files, data=data)

    print("Cloudinary response:", response.status_code)
    print("Cloudinary body:", response.text)

    if response.status_code == 200:
        secure_url = response.json().get("secure_url")
        print("Uploaded URL:", secure_url)
        return secure_url
    else:
        return None


# ----------------------------
# STEP 3: Add comment to Jira
# ----------------------------
def add_comment(issue_key, image_url):
    print("Adding comment to Jira...")

    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/comment"

    payload = {
        "body": f"📎 Uploaded to Cloudinary:\n{image_url}\n\n![image]({image_url})"
    }

    response = requests.post(
        url,
        json=payload,
        auth=(EMAIL, API_TOKEN),
        headers={"Content-Type": "application/json"}
    )

    print("Jira response:", response.status_code, response.text)


# ----------------------------
# BACKGROUND PROCESS
# ----------------------------
def process_request(data):
    try:
        print("Processing request:", data)

        issue_key = data.get("issueKey")
        attachment_url = data.get("attachmentUrl")

        if not attachment_url:
            print("❌ No attachment URL received")
            return

        # Step 1: Download file
        file_bytes = download_attachment(attachment_url)

        if not file_bytes:
            print("❌ Download failed")
            return

        # Step 2: Upload to Cloudinary
        image_url = upload_to_cloudinary(file_bytes)

        if not image_url:
            print("❌ Cloudinary upload failed")
            return

        # Step 3: Add comment
        add_comment(issue_key, image_url)

    except Exception as e:
        print("❌ Error in processing:", str(e))


# ----------------------------
# WEBHOOK (FIXED)
# ----------------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        print("🔥 WEBHOOK HIT")

        raw = request.data
        print("RAW BODY:", raw)

        data = request.get_json(force=True, silent=True)
        print("PARSED DATA:", data)

        if not data:
            print("❌ No JSON received")
            return jsonify({"status": "no data"}), 200

        print("🚀 Starting background thread")

        threading.Thread(target=process_request, args=(data,)).start()

        return jsonify({"status": "accepted"}), 200

    except Exception as e:
        print("❌ Webhook error:", str(e))
        return jsonify({"error": str(e)}), 200


# ----------------------------
# START SERVER (Render)
# ----------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


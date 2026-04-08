from flask import Flask, request, jsonify
import requests
from requests.auth import HTTPBasicAuth
import os
import threading

app = Flask(__name__)


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
    return "image" if ext in image_ext else "raw"


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
def upload_to_cloudinary(file_bytes, file_name, issue_key):
    try:
        upload_type = get_upload_type(file_name)

        upload_url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/{upload_type}/upload"

        files = {
            "file": (file_name, file_bytes)
        }

        data = {
            "upload_preset": UPLOAD_PRESET,
            "folder": issue_key
        }

        response = requests.post(upload_url, files=files, data=data)

        print(f"☁️ Uploading {file_name} → folder {issue_key}")

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
# ADD COMMENT (THUMBNAILS)
# ----------------------------
def add_comment(issue_key, file):
    try:
        url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/comment"

        if file["type"] == "image":
            body = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "📎 Uploaded to DAM"}]
                    },
                    {
                        "type": "mediaSingle",
                        "attrs": {"layout": "center"},
                        "content": [
                            {
                                "type": "media",
                                "attrs": {
                                    "type": "external",
                                    "url": file["url"]
                                }
                            }
                        ]
                    }
                ]
            }
        else:
            body = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "📎 Uploaded to DAM"}]
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": file["name"],
                                "marks": [
                                    {
                                        "type": "link",
                                        "attrs": {"href": file["url"]}
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }

        response = requests.post(
            url,
            json={"body": body},
            auth=HTTPBasicAuth(EMAIL, API_TOKEN),
            headers={"Content-Type": "application/json"}
        )

        print(f"💬 Comment added: {file['name']} →", response.status_code)

    except Exception as e:
        print("❌ Comment error:", str(e))


# ----------------------------
# DELETE ATTACHMENT
# ----------------------------
def delete_attachment(attachment_id):
    try:
        url = f"{JIRA_URL}/rest/api/3/attachment/{attachment_id}"

        response = requests.delete(
            url,
            auth=HTTPBasicAuth(EMAIL, API_TOKEN)
        )

        print(f"🗑️ Deleted attachment {attachment_id} →", response.status_code)

    except Exception as e:
        print("❌ Delete error:", str(e))


# ----------------------------
# UPDATE CUSTOM FIELD (FOLDER INFO ONLY)
# ----------------------------
def update_jira_field(issue_key):
    try:
        url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}"

        payload = {
            "fields": {
                "customfield_10107": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"📂 DAM Folder: {issue_key}"
                                }
                            ]
                        },
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Files stored in Cloudinary"
                                }
                            ]
                        }
                    ]
                }
            }
        }

        response = requests.put(
            url,
            json=payload,
            auth=HTTPBasicAuth(EMAIL, API_TOKEN),
            headers={"Content-Type": "application/json"}
        )

        print("📝 Field update:", response.status_code)

    except Exception as e:
        print("❌ Field update error:", str(e))


# ----------------------------
# MAIN PROCESS
# ----------------------------
def process_request(data):
    try:
        print("🚀 Processing webhook...")

        issue_key = data.get("issueKey")
        attachments = data.get("attachments", [])

        if not attachments:
            return

        for attachment in attachments:
            attachment_id = attachment["id"]

            file_bytes, file_name = download_attachment(attachment)

            if not file_bytes:
                continue

            url = upload_to_cloudinary(file_bytes, file_name, issue_key)

            if url:
                file_info = {
                    "name": file_name,
                    "url": url,
                    "type": get_upload_type(file_name)
                }

                delete_attachment(attachment_id)
                add_comment(issue_key, file_info)

        # 🔥 Update field after all uploads
        update_jira_field(issue_key)

        print("🎉 DONE")

    except Exception as e:
        print("❌ Processing error:", str(e))


# ----------------------------
# WEBHOOK
# ----------------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True, silent=True)

        if not data:
            return jsonify({"status": "no data"}), 200

        threading.Thread(target=process_request, args=(data,)).start()

        return jsonify({"status": "accepted"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 200


# ----------------------------
# START SERVER
# ----------------------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

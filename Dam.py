from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Jira config
JIRA_URL = "https://securonix.atlassian.net"
EMAIL = "access@securonix.com"
API_TOKEN = "ATATT3xFfGF0VYPIlIjb04IYcN8WAyWvL48_KNVVlkT2HeXm4j0p-uTflgw6Ob0NO48V4j4P17zSdYwKzNgcBoOWXVWYLL674VTgom69f6vxN2qo9ptzZvMjPKewMOIwG_4nOMeUyx-fbjZg5h8TDACqqIujteJwY_MzjhZgRgkX007dwZjN1fg=F89AF41A"

# Cloudinary config
CLOUD_NAME = "dthbqhoqk"
API_KEY = "579623882578596"
API_SECRET = "BR5oNBqcRf-ahI4UHYU7wDz_9Mc"


def upload_to_cloudinary(file_url):
    upload_url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"

    response = requests.post(
        upload_url,
        data={
            "file": file_url,
            "api_key": API_KEY,
            "timestamp": "1234567890",
            # NOTE: For POC, unsigned upload preset is easier
            "upload_preset": "unsigned_preset"
        }
    )

    return response.json().get("secure_url")


def add_comment(issue_key, image_url):
    url = f"{JIRA_URL}/rest/api/3/issue/{issue_key}/comment"

    payload = {
        "body": f"📎 File uploaded to Cloudinary:\n{image_url}"
    }

    requests.post(
        url,
        json=payload,
        auth=(EMAIL, API_TOKEN),
        headers={"Content-Type": "application/json"}
    )


@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json

    issue_key = data.get("issueKey")
    attachment_url = data.get("attachmentUrl")

    if not attachment_url:
        return jsonify({"error": "No attachment"}), 400

    # Upload to Cloudinary
    image_url = upload_to_cloudinary(attachment_url)

    # Add comment in Jira
    if image_url:
        add_comment(issue_key, image_url)

    return jsonify({"status": "success"})


if __name__ == '__main__':
    app.run(port=5000)
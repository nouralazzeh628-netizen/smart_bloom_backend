import os
from flask import Flask, send_from_directory, abort
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

img_bp = Blueprint("files", __name__)

# Base directory where your images/static files are stored
FILES_DIR = os.environ.get("FILES_DIR", "../static")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "ico"}

def allowed_file(filename):
    # Check the file has a valid extension
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@img_bp.route("/files/<path:filename>", methods=["GET"])
def serve_file(filename):
    # # Sanitize the filename to block path traversal attacks (e.g. ../../etc/passwd)
    # safe_name = secure_filename(filename)
    # if not safe_name:
    #     abort(400, description="Invalid filename.")

    # Reject file types that aren't in the allowlist
    if not allowed_file(filename):
        abort(400, description="File type not allowed.")

    # Resolve the full path and confirm it's inside FILES_DIR
    base = os.path.normpath(os.path.join(os.path.dirname(__file__), "../static"))
    target = os.path.realpath(os.path.join(base, filename))
    if not target.startswith(base + os.sep):
        abort(400, description="Invalid file path.")

    # send_from_directory handles Content-Type and 404 automatically
    return send_from_directory(base, filename)
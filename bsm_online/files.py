from os import name
import os
from flask import (
    Blueprint, flash, g, session, current_app, redirect, render_template, request, url_for, send_from_directory
)
from werkzeug.exceptions import abort

bp = Blueprint('files', __name__)


@bp.route('/files/<path>')
def return_file(path):
    print(f"File Request made from {request.remote_addr} - {path}")
    if os.path.isfile(rf"{current_app.config['UPLOAD_FOLDER']}/{path}"):
        try:
            r = send_from_directory(current_app.config['UPLOAD_FOLDER'], path)
            return r
        except Exception as e:
            print(e)
            abort(500)
    else:
        abort(404, "File doesn't exist")

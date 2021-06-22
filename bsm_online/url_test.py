from flask import (
    Blueprint, flash, g, session, redirect, render_template, request, send_file, url_for
)
import os
import glob

from werkzeug.exceptions import abort
bp = Blueprint('url_test', __name__)


@bp.route('/url/<input>')
def main(input):
    url = request.base_url.strip('http://').split('/')[0]
    upload_path = os.path.normpath('C:/dev/BSM-Online/uploads/')
    if os.path.isfile(f"{upload_path}/{input}"):
        return send_file(f"{upload_path}/{input}")
    else:
        abort(404)

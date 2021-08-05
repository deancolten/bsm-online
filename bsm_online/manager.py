import os
import glob
import pickle
from flask import (
    Blueprint, flash, g, session, current_app, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
from time import time
from bsm_online.auth import login_required
from bsm_online.db import get_db

from bsm import Manager, Episode

bp = Blueprint('manager', __name__)


# ********FUNCTIONS********


def get_podcast(id):
    podcast = get_db().execute(
        'SELECT p.id, podcast_name, podcast_id, token, user_id'
        ' FROM podcast p JOIN user u ON p.user_id = u.id'
        ' WHERE p.id = ?',
        (id,)
    ).fetchone()

    if podcast is None:
        abort(404, f"Podcast with ID {id} doesn't exist")
    if podcast['user_id'] != g.user['id']:
        abort(403)

    return podcast


def get_manager(id, token):
    """
    Get a manager from id and token, as well as the bsm manager cache if it is saved in the database
    """
    try:
        c = get_db().execute(
            'SELECT manager_blob FROM podcast p'
            ' WHERE p.podcast_id = ?',
            (id,)
        ).fetchone()
        m = pickle.loads(c['manager_blob'])
        return m
    except Exception as inst:
        print(type(inst), " - ", inst)
        return Manager(id, token)


def update_manager(i_manager):
    """
    Update session to include cache info for BSM_Manager. Avoids making too many API calls to buzzsprout
    """

    db = get_db()
    blob = pickle.dumps(i_manager)
    db.execute(
        'UPDATE podcast'
        ' SET manager_blob = ?'
        ' WHERE podcast_id = ?',
        (blob, i_manager.id)
    )
    db.commit()


# VIEWS***********
# ***************************
# ***************************************
# ****************************************************
# **************************************************************
# *************************************************************************
# ************************************************************************************

@bp.route('/')
@login_required
def manager():
    db = get_db()
    podcasts = db.execute(
        'SELECT * FROM podcast p'
        ' WHERE p.user_id = ?',
        (g.user['id'],)
    ).fetchall()

    return render_template('manager/manager.html', podcasts=podcasts)


@ bp.route('/<int:id>/details')
@ login_required
def details(id):
    p = get_podcast(id)
    manager = get_manager(p['podcast_id'], p['token'])
    eps = manager.get_all_episodes()[0:20]
    update_manager(manager)

    return render_template('manager/details.html', podcast=p, eps=eps)


@ bp.route('/create', methods=('GET', 'POST'))
@ login_required
def create():
    if request.method == 'POST':
        podcast_name = request.form['podcast_name']
        podcast_id = request.form['podcast_id']
        token = request.form['token']
        error = None

        if not podcast_name:
            error = "A Name is required"
        elif not podcast_id:
            error = "An ID is required"
        elif not podcast_id.isnumeric():
            error = "Invalid ID"
        elif not token:
            error = "A token is required"
        elif not Manager(podcast_id, token).ok():
            error = "No Buzzsprout Account with given ID and Token"
        if error is not None:
            flash(error)

        else:
            db = get_db()
            db.execute(
                'INSERT INTO podcast (podcast_id, token, podcast_name, user_id)'
                ' VALUES (?, ?, ?, ?)',
                (podcast_id, token, podcast_name, g.user['id'])
            )
            db.commit()
            return redirect(url_for('manager.manager'))
    return render_template('manager/create.html')


@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    podcast = get_podcast(id)

    if request.method == 'POST':
        podcast_name = request.form['podcast_name']
        podcast_id = request.form['podcast_id']
        token = request.form['token']

        error = None

        if not podcast_name:
            error = "A Name is required"
        elif not podcast_id:
            error = "An ID is required"
        elif not podcast_id.isnumeric():
            error = "Invalid ID"
        elif not token:
            error = "A token is required"
        elif not Manager(podcast_id, token).ok():
            error = "No Buzzsprout Account with given ID and Token"
        if error is not None:
            flash(error)

        else:
            db = get_db()
            db.execute(
                'UPDATE podcast SET podcast_name = ?, podcast_id = ?, token = ?'
                ' WHERE id = ?',
                (podcast_name, podcast_id, token, id)
            )
            db.commit()
            return redirect(url_for('manager.manager'))
    return render_template('manager/update.html', podcast=podcast)


@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_podcast(id)
    db = get_db()
    db.execute('DELETE FROM podcast WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('manager.manager'))


@ bp.route('/batch_upload', methods=('GET', 'POST'))
@ login_required
def batch_upload():
    id = g.user['id']
    upload_folder = current_app.config['UPLOAD_FOLDER']

    # ****POST****
    if request.method == 'POST':
        # TERRIBLE way of deleteing files after upload.
        # Doing a remove at the end of the function throws an exception.
        # Maybe changeing the scope of the file.save() and os.remove()??
        # *********************
        # uploads_to_rem = glob.glob(f"{upload_folder}/*")
        # for f in uploads_to_rem:
        #     os.remove(f)
        # First find all podcast IDs in the request.form
        form_pods = []
        for i in request.form:
            try:
                p = i.split('_')[0]
                if p not in form_pods:
                    form_pods.append(p)
            except:
                pass

        # Get podcast, create manager
        for id_value in form_pods:
            p_title = request.form[f"{id_value}_title"]

            if f"{id_value}_post" not in request.form.keys():
                continue
            pod = get_podcast(id_value)
            if pod['user_id'] != g.user['id']:
                abort(403)

            manager = get_manager(pod['podcast_id'], pod['token'])

        # Get File
            try:
                u_file = request.files[F"{id_value}_file"]
                if u_file and not u_file.filename.lower().endswith('.mp3'):
                    flash("Filetype must be .mp3")
                    return redirect(url_for('manager.batch_upload'))
                filename = f"{id}-{id_value}-{int(time())}.mp3"
                u_file.save(os.path.join(
                    upload_folder, filename))
            except Exception as e:
                print('Batch Upload Error - ', type(e))

        # Upload Episode
            file_url = f"{request.url_root[:-1]}{str(url_for('files.return_file', path=filename))}"
            print(file_url)
            e_title = p_title
            if e_title == '':
                e_title = 'Untitled Episode'
            e = Episode(
                **{
                    'title': e_title,
                    'description': request.form[f"{id_value}_description"],
                    'audio_url': file_url
                }
            )

            bsmr = manager.post_episode(episode=e)
            print(bsmr)

        # Make Public if checked
            if f"{id_value}_public" in request.form.keys():
                manager.set_episode_public(bsmr.id)

        flash("Podcasts Uploaded!")
        return redirect(url_for('manager.manager'))
# ****GET*****
    db = get_db()
    podcasts = db.execute(
        'SELECT * FROM podcast p'
        ' WHERE p.user_id = ?',
        (g.user['id'],)
    ).fetchall()

    return render_template('manager/batch_upload.html', podcasts=podcasts)


@ bp.route('/<int:id>/details/<int:epid>/publish_conf', methods=('GET', 'POST'))
@ login_required
def publish_conf(id, epid):
    if request.method == 'POST':
        for i in request.form.keys():
            print(i)
            print(request.form[i])
        pod = get_podcast(id)
        if pod['user_id'] != g.user['id']:
            abort(403)
        manager = get_manager(pod['podcast_id'], pod['token'])
        if 'public' in request.form.keys():
            manager.set_episode_public(epid)
        else:
            manager.set_episode_private(epid)

        return redirect(url_for('manager.details', id=id))

    pod = get_podcast(id)
    m = Manager(pod['podcast_id'], pod['token'])
    ep = m.get_episode_by_id(epid)

    return render_template('manager/publish_conf.html', episode=ep)


@ bp.route('/<int:id>/details/<int:epid>/edit', methods=('GET', 'POST'))
@ login_required
def episode_edit(id, epid):
    if request.method == 'POST':
        pod = get_podcast(id)
        m = get_manager(pod['podcast_id'], pod['token'])
        private = True
        if 'not_private' in request.form.keys():
            private = False

        changes = {
            'title': (request.form['title']),
            'description': (request.form['description']),
            'private': private
        }
        ep = m.get_episode_by_id(epid)
        r = m.update_episode(ep, **changes)
        flash("Episode Updated")
        if not r.ok:
            flash("Response Error!")
            return render_template('manager/episode_edit.html', episode=ep)

        return redirect(url_for('manager.details', id=id))

    pod = get_podcast(id)
    m = get_manager(pod['podcast_id'], pod['token'])
    m._update()
    ep = m.get_episode_by_id(epid)

    update_manager(m)

    return render_template('manager/episode_edit.html', episode=ep)

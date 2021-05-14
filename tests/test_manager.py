import pytest
from dotenv import load_dotenv
from bsm_online.db import get_db
from bsm import Manager
from random import randint
from time import sleep
from werkzeug.datastructures import FileStorage
import os

load_dotenv()
POD_TEST_ID = os.environ.get("POD_TEST_ID")
POD_TEST_ID_2 = os.environ.get("POD_TEST_ID_2")
POD_TEST_TOKEN = os.environ.get("POD_TEST_TOKEN")

# ************ FUNCTIONS **************************************


def get_test_manager():
    """Returns a BSM Manager"""
    m = Manager(POD_TEST_ID, POD_TEST_TOKEN)
    assert m.ok()
    return m


def get_test_int():
    """Returns random int for testing"""
    return randint(0, 200)
# **************************************************************

# ************ TESTS *******************************************


def test_manager_home(client, auth):
    response = client.get('/', follow_redirects=True)
    assert b"Login" in response.data
    assert b"Register" in response.data

    auth.login()
    response = client.get('/')
    assert b'Logout' in response.data
    assert b'1734313' in response.data
    assert b'Test' in response.data
    assert b'href="/1/update"' in response.data


@pytest.mark.parametrize('path', (
    '/create',
    '/1/update',
    '/1/details',
    '/batch_upload'

))
def test_login_required_get(client, path):
    response = client.get(path)
    assert response.headers['Location'] == 'http://localhost/auth/login'


@pytest.mark.parametrize('path', (
    '/create',
    '/1/update',
    '/1/delete',
    '/batch_upload'

))
def test_login_required_post(client, path):
    response = client.post(path)
    assert response.headers['Location'] == 'http://localhost/auth/login'


@pytest.mark.parametrize('path', (
    '/2/update',
    '/2/delete',
    '/2/details/1/publish_conf',
    '/2/details/1/edit',
))
def test_exists_required_post(client, auth, path):
    auth.login()
    assert client.post(path).status_code == 404


@pytest.mark.parametrize('path', (
    '/2/update',
    '/2/details',
    '/2/details/1/publish_conf',
    '/2/details/1/edit',
))
def test_exists_required_get(client, auth, path):
    auth.login()
    assert client.get(path).status_code == 404


def test_create(client, auth, app):
    auth.login()
    assert client.get('/create').status_code == 200
    client.post(
        '/create', data={'podcast_name': 'New Podcast', 'podcast_id': POD_TEST_ID_2, 'token': POD_TEST_TOKEN})

    with app.app_context():
        db = get_db()
        count = db.execute('SELECT COUNT(id) FROM podcast').fetchone()[0]
        assert count == 2


def test_delete(client, auth, app):
    auth.login()
    response = client.post('/1/delete')
    assert response.headers['Location'] == 'http://localhost/'

    with app.app_context():
        db = get_db()
        assert db.execute(
            'SELECT * FROM podcast WHERE id = 1').fetchone() is None


def test_update(client, app, auth):
    auth.login()
    response = client.post('/1/update', data={
        'podcast_name': "UPDATED",
        'podcast_id': POD_TEST_ID_2,
        'token': POD_TEST_TOKEN
    })
    assert response.headers['Location'] == 'http://localhost/'

    with app.app_context():
        db = get_db()
        index = db.execute(
            'SELECT podcast_name, podcast_id, token'
            ' FROM podcast WHERE id = 1'
        ).fetchone()
        assert index['podcast_name'] == "UPDATED"
        assert str(index['podcast_id']) == POD_TEST_ID_2
        assert index['token'] == POD_TEST_TOKEN


@pytest.mark.parametrize('path', (
    '/create',
    '/1/update'
))
def test_validate_podcast_buzzsprout(client, auth, path):
    auth.login()
    response = client.post(
        path,
        data={'podcast_name': 'Name',
              'podcast_id': POD_TEST_ID, 'token': 'BAD TOKEN'},
        follow_redirects=True
    )
    assert b'No Buzzsprout Account with given ID and Token' in response.data


def test_details(client, auth):
    auth.login()
    response = client.get('/1/details')
    assert b'Test' in response.data
    assert b'Publish' in response.data
    assert b'Edit' in response.data
    assert b'Published' in response.data
    assert b'card-body' in response.data


def test_episode_edit(client, auth):
    m = get_test_manager()
    test_num = get_test_int()
    test_title = f"Title {test_num}"
    test_description = f"Description with value {test_num}"
    ep = m.get_all_episodes()[0]

    auth.login()
    response = client.get(f'/1/details/{ep.id}/edit')
    assert response.status_code == 200

    response = client.post(
        f'/1/details/{ep.id}/edit',
        follow_redirects=True,
        data={
            'title': test_title,
            'description': test_description
        })
    assert str.encode(test_title) in response.data


def test_episode_publish_conf(client, auth):
    m = get_test_manager()
    ep = m.get_all_episodes()[0]
    private = ep.private
    auth.login()
    response = client.get(f'/1/details/{ep.id}/publish_conf')
    if private:
        assert b'public' in response.data
        print("first check")
        response = client.post(f'/1/details/{ep.id}/publish_conf',
                               data={
                                   'public': 'public'
                               },
                               follow_redirects=True)
        assert response.status_code == 200
        sleep(1)
        response = client.get(
            f'/1/details/{ep.id}/publish_conf')
        assert b'private' in response.data

    else:
        assert b'private' in response.data
        print("first check")
        response = client.post(f'/1/details/{ep.id}/publish_conf',
                               data={
                                   'private': 'private'
                               },
                               follow_redirects=True)
        assert response.status_code == 200
        sleep(1)
        response = client.get(
            f'/1/details/{ep.id}/publish_conf')
        assert b'public' in response.data


def test_batch_upload(client, auth, app):
    auth.login()
    client.post(
        '/create', data={'podcast_name': 'Test 2', 'podcast_id': POD_TEST_ID_2, 'token': POD_TEST_TOKEN})
    response = client.get('/batch_upload')
    assert b'Test' in response.data
    assert b'Test 2' in response.data

    num = get_test_int()
    title = f"Unit Test {num}"
    description = f"Unit Test {num}"

    file_1 = FileStorage(
        stream=open('testfile2.mp3', 'rb'),
        name='1_file',
        content_type='audio/mpeg'
    )
    file_2 = FileStorage(
        stream=open('testfile2.mp3', 'rb'),
        name='2_file',
        content_type='audio/mpeg'
    )

    up_data = {
        '1_post': '1_post',
        '1_title': title,
        "1_description": description,
        '1_public': 'ok',
        '1_file': file_1,
        '2_post': '2_post',
        '2_title': title,
        "2_description": description,
        '2_public': 'ok',
        '2_file': file_2
    }
    response = client.post(
        '/batch_upload',
        follow_redirects=True,
        data=up_data,
        content_type='multipart/form-data'
    )
    assert response.status_code == 200
    response = client.get('/1/details')
    assert title.encode() in response.data
    response = client.get('/2/details')
    assert title.encode() in response.data

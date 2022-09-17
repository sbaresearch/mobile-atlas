from app import app


def test_register_without_values():
    with app.test_client() as client:
        response = client.post('/wireguard/register')
        assert response.status_code == 400


def test_register_with_incorrect_values():
    with app.test_client() as client:
        data = {'mac': '123', 'publickey': '123'}
        response = client.post('/wireguard/register', data=data)
        assert response.status_code == 400

        data = {'mac': '11:22:33:44:55:66', 'publickey': '123'}
        response = client.post('/wireguard/register', data=data)
        assert response.status_code == 400

        data = {'mac': '123', 'publickey': 'kagRII3IhFHQoaEowld/TkpOf9F/drlbnFkPUzfSzF0='}
        response = client.post('/wireguard/register', data=data)
        assert response.status_code == 400


def test_register_with_unknown_mac():
    with app.test_client() as client:
        data = {'mac': '11:22:33:44:55:66', 'publickey': 'kagRII3IhFHQoaEowld/TkpOf9F/drlbnFkPUzfSzF0='}
        response = client.post('/wireguard/register', data=data)
        assert response.status_code == 403


def test_register_successful():
    with app.test_client() as client:
        data = {'mac': '11:22:33:44:55:66', 'publickey': 'kagRII3IhFHQoaEowld/TkpOf9F/drlbnFkPUzfSzF0='}
        response = client.post('/wireguard/register', data=data)
        assert response.status_code == 403




    # flask_app = create_app('flask_test.cfg')

    # Create a test client using the Flask application configured for testing
    # with flask_app.test_client() as test_client:
    #     response = test_client.get('/')
    # assert True

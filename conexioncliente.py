from app import app, init_db

init_db()

client = app.test_client()

def register(username, password):
    return client.post('/registro', data={'username': username, 'password': password}, follow_redirects=True)

def login(username, password):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)

def addpet(name):
    return client.post('/addpet', data={'name': name, 'description':'desc','age':'1','species':'perro','gender':'M'}, follow_redirects=True)

if __name__ == '__main__':
    print('Testing register...')
    print(register('testuser','testpass').status)
    print('Testing login...')
    print(login('testuser','testpass').status)
    print('Testing addpet (requires admin) - skipping if not admin')
from app import app, init_db, get_db_connection, get_mysql_conn


def run_test():
    init_db()
    client = app.test_client()

    # login como admin
    r = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    print('Login status code:', r.status_code)

    # agregar mascota
    r2 = client.post('/addpet', data={'name': 'PruebaBot', 'description': 'desc', 'age': '2', 'species': 'perro', 'gender': 'M'}, follow_redirects=True)
    print('Addpet status code:', r2.status_code)

    # leer SQLite
    conn = get_db_connection()
    rows = conn.execute('SELECT id, name, mysql_id FROM pets').fetchall()
    print('SQLite pets:')
    for row in rows:
        print(dict(row))
    conn.close()

    # leer MySQL
    try:
        mcnx = get_mysql_conn()
        mcur = mcnx.cursor()
        mcur.execute('SELECT id, name, species, age FROM pets')
        mrows = mcur.fetchall()
        print('MySQL pets:')
        for r in mrows:
            print(r)
        mcur.close()
        mcnx.close()
    except Exception as e:
        print('Error leyendo MySQL:', e)


if __name__ == '__main__':
    run_test()

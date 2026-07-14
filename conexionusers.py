from app import init_db, get_db_connection, get_mysql_conn


def migrate_users():
    init_db()
    conn = get_db_connection()
    users = conn.execute('SELECT id, username, password, is_admin FROM users WHERE mysql_id IS NULL').fetchall()
    if not users:
        print('No hay usuarios para migrar.')
        conn.close()
        return

    mcnx = None
    try:
        mcnx = get_mysql_conn()
        mcur = mcnx.cursor()
    except Exception as e:
        print('No se pudo conectar a MySQL:', e)
        conn.close()
        return

    migrated = 0
    for u in users:
        try:
            mcur.execute('INSERT INTO users (username, password, is_admin) VALUES (%s, %s, %s)',
                         (u['username'], u['password'], int(u['is_admin'])))
            mysql_id = mcur.lastrowid
            mcnx.commit()
            conn.execute('UPDATE users SET mysql_id = ? WHERE id = ?', (mysql_id, u['id']))
            conn.commit()
            migrated += 1
            print(f'Migrado user sqlite id={u["id"]} -> mysql id={mysql_id}')
        except Exception as e:
            print(f'Error migrando usuario {u["username"]}:', e)

    mcur.close()
    mcnx.close()
    conn.close()
    print('Usuarios migrados:', migrated)


def migrate_requests():
    conn = get_db_connection()
    rows = conn.execute('SELECT id, user_id, pet_id, status FROM requests WHERE mysql_id IS NULL').fetchall()
    if not rows:
        print('No hay solicitudes para migrar.')
        conn.close()
        return

    try:
        mcnx = get_mysql_conn()
        mcur = mcnx.cursor()
    except Exception as e:
        print('No se pudo conectar a MySQL:', e)
        conn.close()
        return

    migrated = 0
    for r in rows:
        # obtener mysql ids de user y pet
        urow = conn.execute('SELECT mysql_id FROM users WHERE id = ?', (r['user_id'],)).fetchone()
        prow = conn.execute('SELECT mysql_id FROM pets WHERE id = ?', (r['pet_id'],)).fetchone()
        if not urow or not urow['mysql_id'] or not prow or not prow['mysql_id']:
            print(f'Se omite request sqlite id={r["id"]} por falta de mapping user/pet')
            continue
        try:
            mcur.execute('INSERT INTO requests (user_id, pet_id, status) VALUES (%s, %s, %s)',
                         (int(urow['mysql_id']), int(prow['mysql_id']), r['status']))
            mysql_req = mcur.lastrowid
            mcnx.commit()
            conn.execute('UPDATE requests SET mysql_id = ? WHERE id = ?', (mysql_req, r['id']))
            conn.commit()
            migrated += 1
            print(f'Migrado request sqlite id={r["id"]} -> mysql id={mysql_req}')
        except Exception as e:
            print(f'Error migrando request id={r["id"]}:', e)

    mcur.close()
    mcnx.close()
    conn.close()
    print('Requests migradas:', migrated)


if __name__ == '__main__':
    migrate_users()
    migrate_requests()

from app import get_db_connection, get_mysql_conn, init_db

def migrate_pets():
    # asegurar esquema local
    init_db()
    conn = get_db_connection()
    cur = conn.cursor()
    rows = conn.execute('SELECT id, name, description, age, image, species, gender FROM pets WHERE mysql_id IS NULL').fetchall()
    if not rows:
        print('No hay mascotas pendientes de migrar.')
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
        sqlite_id = r['id']
        name = r['name']
        description = r['description'] or ''
        age = r['age'] or ''
        image = r['image'] or ''
        species = r['species'] or ''
        gender = r['gender'] or ''
        try:
            mcur.execute(
                'INSERT INTO pets (name, description, age, image, species, gender) VALUES (%s, %s, %s, %s, %s, %s)',
                (name, description, age, image, species, gender)
            )
            mysql_id = mcur.lastrowid
            mcnx.commit()
            conn.execute('UPDATE pets SET mysql_id = ? WHERE id = ?', (mysql_id, sqlite_id))
            conn.commit()
            migrated += 1
            print(f'Migrado sqlite id={sqlite_id} -> mysql id={mysql_id}')
        except Exception as e:
            print(f'Error migrando sqlite id={sqlite_id}:', e)

    mcur.close()
    mcnx.close()
    conn.close()
    print(f'Migración completada. Total migradas: {migrated}')

if __name__ == '__main__':
    migrate_pets()

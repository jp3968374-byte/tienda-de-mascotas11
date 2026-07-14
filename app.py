from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import mysql.connector


MYSQL_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'tiendademascotas',
    'port': 3306,
}


def get_mysql_conn():
    return mysql.connector.connect(**MYSQL_CONFIG)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'img')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = 'cambiar_por_una_clave_segura'



def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS pets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        age TEXT,
        image TEXT,
        species TEXT,
        gender TEXT
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        pet_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(pet_id) REFERENCES pets(id)
    )
    ''')
    conn.commit()

   
    cur.execute("SELECT * FROM users WHERE username = ?", ('admin',))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, 1)",
                    ('admin', generate_password_hash('admin123')))
        conn.commit()

    conn.close()

    conn = get_db_connection()
    cols = [c['name'] for c in conn.execute("PRAGMA table_info('pets')").fetchall()]
    if 'species' not in cols:
        conn.execute("ALTER TABLE pets ADD COLUMN species TEXT")
    if 'gender' not in cols:
        conn.execute("ALTER TABLE pets ADD COLUMN gender TEXT")
    if 'mysql_id' not in cols:
        conn.execute("ALTER TABLE pets ADD COLUMN mysql_id INTEGER")

    cols_u = [c['name'] for c in conn.execute("PRAGMA table_info('users')").fetchall()]
    if 'mysql_id' not in cols_u:
        conn.execute("ALTER TABLE users ADD COLUMN mysql_id INTEGER")

    cols_r = [c['name'] for c in conn.execute("PRAGMA table_info('requests')").fetchall()]
    if 'mysql_id' not in cols_r:
        conn.execute("ALTER TABLE requests ADD COLUMN mysql_id INTEGER")
    conn.commit()
    conn.close()


@app.route('/')
def index():
    conn = get_db_connection()
    pets = conn.execute('SELECT * FROM pets').fetchall()
    conn.close()
    return render_template('catalogo.html', pets=pets)


@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                        (username, generate_password_hash(password)))
            sqlite_id = cur.lastrowid
            conn.commit()
            
            try:
                mcnx = get_mysql_conn()
                mcur = mcnx.cursor()
                mcur.execute('INSERT INTO users (username, password, is_admin) VALUES (%s, %s, %s)',
                             (username, generate_password_hash(password), 0))
                mysql_id = mcur.lastrowid
                mcnx.commit()
                mcur.close()
                mcnx.close()
               
                conn.execute('UPDATE users SET mysql_id = ? WHERE id = ?', (mysql_id, sqlite_id))
                conn.commit()
            except Exception as e:
                print('Error sincronizando usuario con MySQL:', e)

            flash('Registro exitoso. Ahora inicia sesión.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('El usuario ya existe.', 'danger')
        finally:
            conn.close()
    return render_template('registro.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = bool(user['is_admin'])
            flash('Has iniciado sesión correctamente.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada.', 'info')
    return redirect(url_for('index'))


def login_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Acceso denegado: administrador solamente.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated


@app.route('/admin')
@login_required
@admin_required
def admin():
    conn = get_db_connection()
    pets = conn.execute('SELECT * FROM pets').fetchall()
    users = conn.execute('SELECT id, username, is_admin, password FROM users').fetchall()
    conn.close()
    return render_template('admin.html', pets=pets, users=users)


@app.route('/admin/user/<int:user_id>/toggle_admin', methods=['POST'])
@login_required
@admin_required
def toggle_admin_user(user_id):
   
    if session.get('user_id') == user_id:
        flash('No puedes cambiar tu propio rol.', 'danger')
        return redirect(url_for('admin'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('admin'))
    new_role = 0 if user['is_admin'] else 1
    conn.execute('UPDATE users SET is_admin = ? WHERE id = ?', (new_role, user_id))
    conn.commit()
    conn.close()
    flash('Rol de usuario actualizado.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    
    if session.get('user_id') == user_id:
        flash('No puedes eliminar tu propia cuenta.', 'danger')
        return redirect(url_for('admin'))
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('admin'))
   
    conn.execute('DELETE FROM requests WHERE user_id = ?', (user_id,))
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash('Usuario eliminado.', 'info')
    return redirect(url_for('admin'))


@app.route('/admin/user/<int:user_id>/set_password', methods=['GET', 'POST'])
@login_required
@admin_required
def set_user_password(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT id, username FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('admin'))
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if not new_password:
            flash('Introduce una contraseña válida.', 'danger')
            conn.close()
            return redirect(url_for('set_user_password', user_id=user_id))
        hashed = generate_password_hash(new_password)
        conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed, user_id))
        conn.commit()
        conn.close()
        flash('Contraseña actualizada correctamente.', 'success')
        return redirect(url_for('admin'))
    conn.close()
    return render_template('set_password.html', user=user)


@app.route('/addpet', methods=['GET', 'POST'])
@login_required
@admin_required
def addpet():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        age = request.form['age']
       
        image_file = request.files.get('image_file')
        image_value = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            
            import uuid
            filename = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            image_file.save(save_path)
            image_value = filename
        else:
           
            image_value = request.form.get('image')

        species = request.form.get('species')
        gender = request.form.get('gender')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO pets (name, description, age, image, species, gender) VALUES (?, ?, ?, ?, ?, ?)',
                 (name, description, age, image_value, species, gender))
        sqlite_id = cur.lastrowid
        conn.commit()
        
        try:
            mcnx = get_mysql_conn()
            mcur = mcnx.cursor()
            mcur.execute("INSERT INTO pets (name, description, age, image, species, gender) VALUES (%s, %s, %s, %s, %s, %s)",
                         (name, description, age, image_value or '', species, gender))
            mysql_id = mcur.lastrowid
            mcnx.commit()
            mcur.close()
            mcnx.close()
            
            conn.execute('UPDATE pets SET mysql_id = ? WHERE id = ?', (mysql_id, sqlite_id))
            conn.commit()
        except Exception as e:
            print('Error sincronizando con MySQL:', e)
        conn.close()
        flash('Mascota agregada.', 'success')
        return redirect(url_for('admin'))
    return render_template('addmascotas.html')


@app.route('/editpet/<int:pet_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editpet(pet_id):
    conn = get_db_connection()
    pet = conn.execute('SELECT * FROM pets WHERE id = ?', (pet_id,)).fetchone()
    if not pet:
        conn.close()
        flash('Mascota no encontrada.', 'danger')
        return redirect(url_for('admin'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        age = request.form['age']
        image_file = request.files.get('image_file')
        image_value = pet['image']
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            import uuid
            filename = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            image_file.save(save_path)
            image_value = filename
        else:
            
            form_img = request.form.get('image')
            if form_img:
                image_value = form_img

        species = request.form.get('species')
        gender = request.form.get('gender')

        conn.execute('UPDATE pets SET name = ?, description = ?, age = ?, image = ?, species = ?, gender = ? WHERE id = ?',
                     (name, description, age, image_value, species, gender, pet_id))
        conn.commit()
        conn.close()
       
        try:
           
            conn2 = get_db_connection()
            row = conn2.execute('SELECT mysql_id FROM pets WHERE id = ?', (pet_id,)).fetchone()
            conn2.close()
            if row and row['mysql_id']:
                mcnx = get_mysql_conn()
                mcur = mcnx.cursor()
                mcur.execute('UPDATE pets SET name=%s, description=%s, age=%s, image=%s, species=%s, gender=%s WHERE id=%s',
                             (name, description, age, image_value or '', species, gender, int(row['mysql_id'])))
                mcnx.commit()
                mcur.close()
                mcnx.close()
        except Exception as e:
            print('Error sincronizando edición con MySQL:', e)
        flash('Mascota actualizada.', 'success')
        return redirect(url_for('admin'))

    conn.close()
    return render_template('editproductos.html', pet=pet)


@app.route('/deletepet/<int:pet_id>', methods=['POST'])
@login_required
@admin_required
def deletepet(pet_id):
    conn = get_db_connection()
    pet = conn.execute('SELECT * FROM pets WHERE id = ?', (pet_id,)).fetchone()
    if not pet:
        conn.close()
        flash('Mascota no encontrada.', 'danger')
        return redirect(url_for('admin'))

    
    img = pet['image']
    if img and not str(img).startswith('http'):
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, img))
        except Exception:
            pass

   
    row = conn.execute('SELECT mysql_id FROM pets WHERE id = ?', (pet_id,)).fetchone()
    conn.execute('DELETE FROM requests WHERE pet_id = ?', (pet_id,))
    
    conn.execute('DELETE FROM pets WHERE id = ?', (pet_id,))
    conn.commit()
    
    try:
        if row and row['mysql_id']:
            mcnx = get_mysql_conn()
            mcur = mcnx.cursor()
            mcur.execute('DELETE FROM pets WHERE id = %s', (int(row['mysql_id']),))
            mcnx.commit()
            mcur.close()
            mcnx.close()
    except Exception as e:
        print('Error borrando en MySQL:', e)
    conn.close()
    flash('Mascota eliminada correctamente.', 'info')
    return redirect(url_for('admin'))


@app.route('/adopt/<int:pet_id>', methods=['POST'])
@login_required
def adopt(pet_id):
    
    if session.get('is_admin'):
        flash('Los administradores no pueden solicitar adopciones.', 'danger')
        return redirect(url_for('index'))

    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO requests (user_id, pet_id) VALUES (?, ?)', (user_id, pet_id))
    sqlite_req_id = cur.lastrowid
    conn.commit()
   
    try:
        
        row_u = conn.execute('SELECT mysql_id FROM users WHERE id = ?', (user_id,)).fetchone()
        row_p = conn.execute('SELECT mysql_id FROM pets WHERE id = ?', (pet_id,)).fetchone()
        mysql_user = int(row_u['mysql_id']) if row_u and row_u['mysql_id'] else None
        mysql_pet = int(row_p['mysql_id']) if row_p and row_p['mysql_id'] else None
        if mysql_user and mysql_pet:
            mcnx = get_mysql_conn()
            mcur = mcnx.cursor()
            mcur.execute('INSERT INTO requests (user_id, pet_id, status) VALUES (%s, %s, %s)',
                         (mysql_user, mysql_pet, 'pending'))
            mysql_req_id = mcur.lastrowid
            mcnx.commit()
            mcur.close()
            mcnx.close()
            
            conn.execute('UPDATE requests SET mysql_id = ? WHERE id = ?', (mysql_req_id, sqlite_req_id))
            conn.commit()
    except Exception as e:
        print('Error sincronizando solicitud con MySQL:', e)

    conn.close()
    flash('Solicitud de adopción enviada.', 'success')
    return redirect(url_for('index'))


@app.route('/requests')
@login_required
@admin_required
def requests_list():
    conn = get_db_connection()
    rows = conn.execute('''
    SELECT r.id, r.status, r.created_at, u.username, p.name as pet_name
    FROM requests r
    LEFT JOIN users u ON r.user_id = u.id
    LEFT JOIN pets p ON r.pet_id = p.id
    ORDER BY r.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('solicitudes.html', requests=rows)


@app.route('/request/<int:request_id>/accept', methods=['POST'])
@login_required
@admin_required
def accept_request(request_id):
    conn = get_db_connection()
    r = conn.execute('SELECT * FROM requests WHERE id = ?', (request_id,)).fetchone()
    if not r:
        conn.close()
        flash('Solicitud no encontrada.', 'danger')
        return redirect(url_for('requests_list'))
    conn.execute('UPDATE requests SET status = ? WHERE id = ?', ('accepted', request_id))
    conn.commit()
    conn.close()
    flash('Solicitud aceptada.', 'success')
    return redirect(url_for('requests_list'))


@app.route('/request/<int:request_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_request(request_id):
    conn = get_db_connection()
    r = conn.execute('SELECT * FROM requests WHERE id = ?', (request_id,)).fetchone()
    if not r:
        conn.close()
        flash('Solicitud no encontrada.', 'danger')
        return redirect(url_for('requests_list'))
    conn.execute('UPDATE requests SET status = ? WHERE id = ?', ('rejected', request_id))
    conn.commit()
    conn.close()
    flash('Solicitud rechazada.', 'info')
    return redirect(url_for('requests_list'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)

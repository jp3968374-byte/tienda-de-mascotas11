import mysql.connector

try:
    conexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="datadeanimales",
    )
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM datadeanimales")
    for fila in cursor.fetchall():
        print(fila)
except mysql.connector.Error as err:
    print("Error de conexión:", err)
finally:
    try:
        if 'conexion' in locals() and conexion.is_connected():
            conexion.close()
    except NameError:
        pass

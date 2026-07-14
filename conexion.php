<?php
$host = 'TuPasswordSeguro';
$user = 'root';          // tu usuario MySQL
$pass = '';     // tu contraseña
$db   = 'tiendademascotas';

$conn = new mysqli($host, $user, $pass, $db);
if ($conn->connect_error) {
    die("Conexión fallida: " . $conn->connect_error);
}
?>

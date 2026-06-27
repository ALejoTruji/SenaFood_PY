from locust import HttpUser, task, between

# Credenciales de prueba — usa una cuenta real de tu sistema
USUARIO = "alejandrotrujipz@gmail.com"
PASSWORD = "Ptad60741*"

class UsuarioSenaFOOD(HttpUser):
    # Tiempo de espera entre acciones (simula usuario real)
    wait_time = between(2, 5)

    def on_start(self):
        """Se ejecuta cuando el usuario virtual inicia — hace login"""
        # Obtener el CSRF token
        resp = self.client.get("/login/")
        
        # Extraer el CSRF token de las cookies
        csrf_token = self.client.cookies.get("csrftoken", "")
        
        # Hacer login enviando el CSRF token
        self.client.post("/login/", {
            "email": USUARIO,
            "password": PASSWORD,
            "csrfmiddlewaretoken": csrf_token,
        }, headers={"Referer": "https://senafood-production.up.railway.app/login/"})

    @task(5)
    def ver_catalogo(self):
        """Tarea más frecuente — ver el catálogo"""
        self.client.get("/catalogo/", name="GET /catalogo/")

    @task(3)
    def ver_carrito(self):
        """Ver el carrito"""
        self.client.get("/catalogo/carrito/", name="GET /carrito/")

    @task(3)
    def api_notificaciones(self):
        """API de notificaciones — se consulta frecuentemente"""
        self.client.get("/notificaciones/api/contar/", name="API notificaciones")

    @task(2)
    def api_estado_tienda(self):
        """API estado de la tienda"""
        self.client.get("/catalogo/tienda/estado/", name="API tienda")

    @task(1)
    def ver_pqrsf(self):
        """Ver lista de PQRSF"""
        self.client.get("/pqrsf/lista/", name="GET /pqrsf/")
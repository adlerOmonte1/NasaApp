// Esperar a que el DOM esté completamente cargado
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ DOM cargado - inicializando mapa...');
    
    // Inicializar el mapa
    const map = L.map('map').setView([-9.93, -76.24], 5);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    let marker;

    // Configurar fecha mínima como hoy
    const dateInput = document.getElementById('manual-date');
    const today = new Date().toISOString().split('T')[0];
    dateInput.min = today;
    dateInput.value = today;

    console.log('✅ Fecha configurada:', dateInput.value);

    // Función para obtener la ubicación actual
    document.getElementById('get-location-btn').addEventListener('click', function() {
        console.log('📍 Botón de ubicación clickeado');
        if (navigator.geolocation) {
            showLoading();
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    
                    console.log('📍 Ubicación obtenida:', lat, lon);
                    
                    document.getElementById('manual-lat').value = lat.toFixed(6);
                    document.getElementById('manual-lon').value = lon.toFixed(6);
                    
                    updateMapLocation(lat, lon, 'Tu ubicación actual');
                    getWeatherDataFromAPI(lat, lon);
                },
                function(error) {
                    hideLoading();
                    console.error('❌ Error geolocalización:', error);
                    alert('Error al obtener la ubicación: ' + getErrorMessage(error));
                }
            );
        } else {
            alert('La geolocalización no es compatible con este navegador.');
        }
    });

    // Función para obtener datos con coordenadas manuales - VERIFICAR ESTA FUNCIÓN
    document.getElementById('get-manual-btn').addEventListener('click', function() {
        console.log('🔄 Botón consultar datos clickeado - INICIANDO PROCESO');
        
        // Obtener valores de los inputs
        const latInput = document.getElementById('manual-lat');
        const lonInput = document.getElementById('manual-lon');
        const dateInput = document.getElementById('manual-date');
        const timeInput = document.getElementById('manual-time');
        
        console.log('📝 Inputs encontrados:', {
            lat: latInput,
            lon: lonInput,
            date: dateInput,
            time: timeInput
        });
        
        const lat = parseFloat(latInput.value);
        const lon = parseFloat(lonInput.value);
        const date = dateInput.value;
        const time = timeInput.value;
        
        console.log('📊 Valores obtenidos:', {lat, lon, date, time});
        
        // Validaciones
        if (isNaN(lat) || isNaN(lon)) {
            console.error('❌ Coordenadas inválidas');
            alert('Por favor, ingresa coordenadas válidas.');
            return;
        }
        
        if (!date) {
            console.error('❌ Fecha no seleccionada');
            alert('Por favor, selecciona una fecha.');
            return;
        }
        
        console.log('✅ Validaciones pasadas - procediendo con la consulta');
        showLoading();
        
        // Centrar mapa y agregar marcador
        updateMapLocation(lat, lon, 'Ubicación seleccionada');
        
        // Obtener datos del clima desde la API
        getWeatherDataFromAPI(lat, lon, date, time);
    });

    // Función para actualizar la ubicación en el mapa
    function updateMapLocation(lat, lon, popupText) {
        console.log('🗺️ Actualizando mapa:', lat, lon);
        map.setView([lat, lon], 13);
        if (marker) {
            map.removeLayer(marker);
        }
        marker = L.marker([lat, lon]).addTo(map)
            .bindPopup(popupText)
            .openPopup();
    }

    // Función para mostrar estado de carga
    function showLoading() {
        const resultsDiv = document.getElementById('results');
        resultsDiv.style.display = 'block';
        resultsDiv.innerHTML = '<div class="loading">Obteniendo datos climáticos</div>';
        console.log('⏳ Mostrando estado de carga...');
    }

    // Función para obtener mensaje de error de geolocalización
    function getErrorMessage(error) {
        switch(error.code) {
            case error.PERMISSION_DENIED:
                return "Permiso de ubicación denegado.";
            case error.POSITION_UNAVAILABLE:
                return "Información de ubicación no disponible.";
            case error.TIMEOUT:
                return "Tiempo de espera agotado.";
            default:
                return "Error desconocido.";
        }
    }

    // Función para obtener datos del clima desde tu API
    async function getWeatherDataFromAPI(lat, lon, date = null, time = null) {
        console.log('🌤️ Iniciando consulta a API...');
        console.log('📡 Parámetros:', {lat, lon, date, time});
        
        // Si no se proporciona fecha/hora, usar la actual
        if (!date) {
            const now = new Date();
            date = now.toISOString().split('T')[0];
            time = now.toTimeString().split(':')[0] + ':00';
        }
        
        if (!time) {
            time = '14:00';
        }

        console.log('📨 Enviando petición a /api/get_location_data...');
        
        try {
            const response = await fetch('/api/get_location_data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    latitude: lat,
                    longitude: lon,
                    date: date,
                    time: time
                })
            });

            console.log('📥 Respuesta recibida:', response.status, response.statusText);

            if (!response.ok) {
                throw new Error(`Error HTTP: ${response.status} - ${response.statusText}`);
            }

            const data = await response.json();
            console.log('✅ Datos recibidos del backend:', data);
            
            displayResultsFromAPI(data, lat, lon, date, time);
            
        } catch (error) {
            console.error('❌ Error al obtener datos del clima:', error);
            displayError('Error al conectar con el servidor: ' + error.message);
        }
    }

    // Función para mostrar los resultados desde la API
    function displayResultsFromAPI(data, lat, lon, date, time) {
        console.log('🎨 Mostrando resultados...');
        const resultsDiv = document.getElementById('results');
        
        const fechaObj = new Date(date + 'T' + time);
        const fechaFormateada = fechaObj.toLocaleDateString('es-ES');
        const horaFormateada = fechaObj.toLocaleTimeString('es-ES', {hour: '2-digit', minute:'2-digit'});
        
        resultsDiv.innerHTML = `
            <h3>Pronóstico Climatológico</h3>
            <p class="location">${data.departamento || 'N/A'}, ${data.pais || 'N/A'}</p>
            <p class="location">Coordenadas: Lat ${lat.toFixed(4)}, Lon ${lon.toFixed(4)}</p>
            <p class="location">Fecha: ${fechaFormateada} - Hora: ${horaFormateada}</p>
            
            <div class="weather-info">
                <div class="weather-card">
                    <h4>Pronóstico del Modelo</h4>
                    <p style="font-size: 1.2em; line-height: 1.4;">${data.prediccion_modelo || 'No disponible'}</p>
                </div>
                <div class="weather-card">
                    <h4>Temperatura Real Histórica</h4>
                    <p>${data.temperatura_real || 'No disponible'}</p>
                </div>
            </div>
        `;
        
        console.log('✅ Resultados mostrados correctamente');
    }

    // Función para mostrar errores
    function displayError(message) {
        const resultsDiv = document.getElementById('results');
        resultsDiv.innerHTML = `
            <div class="error-message">
                <h3>❌ Error</h3>
                <p>${message}</p>
                <p>Verifica que:</p>
                <ul>
                    <li>El servidor backend esté ejecutándose en puerto 8000</li>
                    <li>La ruta /api/get_location_data exista</li>
                    <li>No haya errores de CORS</li>
                </ul>
            </div>
        `;
    }

    // Agregar evento de clic al mapa para establecer ubicación
    map.on('click', function(e) {
        const lat = e.latlng.lat;
        const lon = e.latlng.lng;
        
        console.log('🗺️ Mapa clickeado:', lat, lon);
        
        document.getElementById('manual-lat').value = lat.toFixed(6);
        document.getElementById('manual-lon').value = lon.toFixed(6);
        
        updateMapLocation(lat, lon, 'Ubicación seleccionada');
    });

    console.log('✅ Aplicación inicializada correctamente');
});
const analyzeBtn    = document.getElementById("analyzeBtn");
const welcomeState  = document.getElementById("welcomeState");
const results       = document.getElementById("results");

const localIp       = document.getElementById("localIp");
const gateway       = document.getElementById("gateway");
const subnetMask    = document.getElementById("subnetMask");
const gatewayStatus = document.getElementById("gatewayStatus");
const gatewayLatency= document.getElementById("gatewayLatency");
const internetStatus= document.getElementById("internetStatus");
const latency       = document.getElementById("latency");
const packetLoss    = document.getElementById("packetLoss");
const diagnosis     = document.getElementById("diagnosis");
const devicesList   = document.getElementById("devices");
const devicesSummary= document.getElementById("devicesSummary");

const summaryTitle  = document.getElementById("summaryTitle");
const summaryText   = document.getElementById("summaryText");
const summaryBadge  = document.getElementById("summaryBadge");

const heroStatusTitle = document.getElementById("heroStatusTitle");
const heroStatusText  = document.getElementById("heroStatusText");
const helperText      = document.getElementById("helperText");

const stepNetwork  = document.getElementById("stepNetwork");
const stepInternet = document.getElementById("stepInternet");
const stepDevices  = document.getElementById("stepDevices");

const cards = document.querySelectorAll(".card");

function setStatusClass(el, cls) {
    el.className = cls;
}

function setProgressState(el, state) {
    el.classList.remove("active", "done");
    if (state) el.classList.add(state);
}

function resetProgress() {
    [stepNetwork, stepInternet, stepDevices].forEach(s => s.classList.remove("active", "done"));
}

function setLoading() {
    localIp.textContent       = "Obteniendo...";
    gateway.textContent       = "Obteniendo...";
    subnetMask.textContent    = "Obteniendo...";
    gatewayStatus.textContent = "Pendiente";
    internetStatus.textContent= "Pendiente";
    gatewayLatency.textContent= "Latencia: revisando...";
    latency.textContent       = "Latencia: revisando...";
    packetLoss.textContent    = "Pérdida: revisando...";
    diagnosis.textContent     = "Analizando...";
    devicesSummary.textContent= "Buscando dispositivos visibles en tu red...";
    devicesList.innerHTML     = "<li>Escaneando la red local...</li>";

    summaryTitle.textContent = "Analizando tu conexión";
    summaryText.textContent  = "Estamos reuniendo datos de tu red local, del gateway y de la salida a internet.";
    summaryBadge.textContent = "En curso";
    setStatusClass(summaryBadge, "badge neutral");

    heroStatusTitle.textContent = "Análisis en progreso";
    heroStatusText.textContent  = "Iremos marcando cada paso a medida que tengamos resultados.";
    helperText.textContent      = "El análisis puede tardar un poco según el tamaño de la red.";

    setStatusClass(gatewayStatus,  "status-pill neutral");
    setStatusClass(internetStatus, "status-pill neutral");
    resetProgress();
    setProgressState(stepNetwork, "active");
    cards.forEach(c => c.classList.add("loading"));
}

function cardDone(...elements) {
    elements.forEach(el => {
        const card = el.closest(".card");
        if (card) card.classList.remove("loading");
    });
}

function renderDevices(devices) {
    devicesList.innerHTML = "";

    if (devices && devices.length > 0) {
        devicesSummary.textContent = `Se detectaron ${devices.length} dispositivo(s) en esta red.`;
        devices.forEach(device => {
            const li       = document.createElement("li");
            const ip       = document.createElement("span");
            const hostname = document.createElement("span");

            ip.className       = "device-ip";
            ip.textContent     = device.ip;
            hostname.className = "device-hostname";
            hostname.textContent = device.hostname || "Nombre no disponible";

            li.appendChild(ip);
            li.appendChild(hostname);
            devicesList.appendChild(li);
        });
        return;
    }

    devicesSummary.textContent = "No encontramos otros dispositivos visibles. Puede ser normal en redes con aislamiento.";
    devicesList.innerHTML = "<li>No se detectaron dispositivos visibles.</li>";
}

function updateSummary(diagnosisText) {
    const t = diagnosisText.toLowerCase();

    if (t.includes("responden correctamente") || t.includes("conexión estable")) {
        summaryTitle.textContent = "Tu red luce saludable";
        summaryText.textContent  = "La red local y la salida a internet respondieron bien durante la revisión.";
        summaryBadge.textContent = "Estable";
        setStatusClass(summaryBadge, "badge good");
        heroStatusTitle.textContent = "Revisión completada";
        heroStatusText.textContent  = "Tu conexión respondió bien y ya tienes un resumen listo para consultar.";
        return;
    }

    if (t.includes("aceptable") || t.includes("moderada") || t.includes("pocos dispositivos")) {
        summaryTitle.textContent = "La conexión funciona, con algunos matices";
        summaryText.textContent  = "Hay servicio, pero encontramos señales que conviene vigilar.";
        summaryBadge.textContent = "Atención";
        setStatusClass(summaryBadge, "badge warn");
        heroStatusTitle.textContent = "Revisión completada";
        heroStatusText.textContent  = "La conexión está disponible, aunque no se comportó de forma ideal.";
        return;
    }

    summaryTitle.textContent = "Detectamos un posible problema";
    summaryText.textContent  = "El análisis encontró señales de fallo o inestabilidad en la conexión.";
    summaryBadge.textContent = "Problema";
    setStatusClass(summaryBadge, "badge bad");
    heroStatusTitle.textContent = "Revisión completada";
    heroStatusText.textContent  = "Ya puedes revisar el diagnóstico principal para entender dónde está el problema.";
}

analyzeBtn.addEventListener("click", () => {
    analyzeBtn.disabled    = true;
    analyzeBtn.textContent = "Analizando...";

    welcomeState.classList.add("hidden");
    results.classList.remove("hidden");
    setLoading();

    const source = new EventSource("/analyze/stream");

    source.addEventListener("network_info", event => {
        const data = JSON.parse(event.data);
        localIp.textContent    = data.local_ip    || "No disponible";
        gateway.textContent    = data.gateway     || "No disponible";
        subnetMask.textContent = data.subnet_mask || "No disponible";

        heroStatusTitle.textContent = "Información de red lista";
        heroStatusText.textContent  = "Ya conocemos la base de tu conexión. Ahora revisamos gateway e internet.";
        setProgressState(stepNetwork,  "done");
        setProgressState(stepInternet, "active");
        cardDone(localIp, gateway, subnetMask);
    });

    source.addEventListener("gateway", event => {
        const data = JSON.parse(event.data);
        gatewayStatus.textContent = data.reachable ? "Responde bien" : "Sin respuesta";
        gatewayLatency.textContent = data.latency_ms !== null
            ? `Latencia: ${data.latency_ms} ms`
            : "Latencia: no disponible";
        setStatusClass(gatewayStatus, data.reachable ? "status-pill good" : "status-pill bad");
        cardDone(gatewayStatus, gatewayLatency);
    });

    source.addEventListener("internet", event => {
        const data = JSON.parse(event.data);
        internetStatus.textContent = data.reachable ? "Con conexión" : "Sin conexión";
        latency.textContent = data.latency_ms !== null
            ? `Latencia: ${data.latency_ms} ms`
            : "Latencia: no disponible";
        packetLoss.textContent = data.packet_loss !== null
            ? `Pérdida: ${data.packet_loss}%`
            : "Pérdida: no disponible";
        setStatusClass(internetStatus, data.reachable ? "status-pill good" : "status-pill bad");

        heroStatusTitle.textContent = "Conectividad revisada";
        heroStatusText.textContent  = data.reachable
            ? "Tu red tiene salida a internet. Solo falta revisar los dispositivos visibles."
            : "La salida a internet no respondió. Terminaremos el escaneo local para darte mejor contexto.";
        setProgressState(stepInternet, "done");
        setProgressState(stepDevices,  "active");
        cardDone(internetStatus, latency, packetLoss);
    });

    source.addEventListener("scan", event => {
        const data = JSON.parse(event.data);
        renderDevices(data.devices);
        setProgressState(stepDevices, "done");
        cardDone(devicesList);
    });

    source.addEventListener("done", event => {
        const data = JSON.parse(event.data);
        const diagnosisText = data.diagnosis || "Sin diagnóstico";
        diagnosis.textContent = diagnosisText;
        updateSummary(diagnosisText);
        cardDone(diagnosis);
        source.close();
        analyzeBtn.disabled    = false;
        analyzeBtn.textContent = "Volver a analizar";
        helperText.textContent = "Puedes volver a ejecutar el análisis cuando quieras.";
    });

    source.onerror = () => {
        source.close();
        cards.forEach(c => c.classList.remove("loading"));
        diagnosis.textContent    = "No fue posible completar el análisis.";
        summaryTitle.textContent = "Análisis interrumpido";
        summaryText.textContent  = "Ocurrió un problema al recibir los resultados. Intenta nuevamente.";
        summaryBadge.textContent = "Error";
        setStatusClass(summaryBadge, "badge bad");
        heroStatusTitle.textContent = "No pudimos terminar la revisión";
        heroStatusText.textContent  = "La conexión con el análisis se interrumpió antes de completarse.";
        analyzeBtn.disabled    = false;
        analyzeBtn.textContent = "Intentar de nuevo";
    };
});

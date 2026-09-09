# Guía: poner el bot a correr en un servidor

El bot no necesita potencia. Necesita **estar encendido sin interrupciones**, **buena latencia a
Polymarket** y **disco suficiente**. Un servidor virtual básico cumple las tres cosas mejor que
cualquier computadora en casa.

## 1. Elegir el servidor

| Requisito | Recomendación | Por qué |
|---|---|---|
| Región | Costa este de EE. UU. (Virginia, Nueva York, Nueva Jersey) | Los servidores de Polymarket están ahí; la ida y vuelta baja de ~150 ms a ~10 ms |
| CPU / RAM | 1-2 vCPU, 2 GB de RAM | El recolector usa un núcleo; el reentrenamiento tarda segundos |
| Disco | 80 GB SSD | Con la retención activa el crecimiento permanente es ~0,5 GB/día |
| Sistema | Ubuntu 24.04 LTS (o Debian 12) | Es lo que prueba `deploy/install.sh` |
| Costo | 5 a 12 USD/mes | Hetzner, DigitalOcean, Vultr, Linode, AWS Lightsail |

Al crearlo, agrega tu **llave SSH** en vez de contraseña. Anota la IP.

> Polymarket restringe el acceso desde varios países. Correr el bot en un servidor en EE. UU. no
> cambia tu situación legal; verifica las condiciones que te aplican antes de conectar dinero.
> Esta guía deja el bot en **paper trading**: no firma órdenes ni toca una wallet.

## 2. Primer acceso y seguridad mínima

```bash
ssh root@IP_DEL_SERVIDOR

# usuario administrador con sudo (no operar como root)
adduser admin && usermod -aG sudo admin
mkdir -p /home/admin/.ssh && cp ~/.ssh/authorized_keys /home/admin/.ssh/ && chown -R admin:admin /home/admin/.ssh

# cortafuegos: solo SSH. El panel NO se expone a internet (se ve por túnel SSH)
apt-get update && apt-get install -y ufw
ufw allow OpenSSH && ufw --force enable

# actualizaciones de seguridad automáticas
apt-get install -y unattended-upgrades && dpkg-reconfigure -plow unattended-upgrades
```

Desde aquí entra como `admin@IP` y usa `sudo`.

## 3. Instalar el bot

```bash
ssh admin@IP_DEL_SERVIDOR
git clone --branch RAMA https://github.com/TU_USUARIO/TU_REPO.git ~/scalper-src
cd ~/scalper-src/polymarket_scalper          # o la raíz, si el proyecto vive ahí
sudo bash deploy/install.sh
```

El script, que se puede repetir sin romper nada:

1. instala Python, git y rsync; pone el reloj en UTC (todas las tablas usan UTC);
2. crea el usuario de servicio `scalper` sin shell y la carpeta `/opt/scalper`;
3. copia el código a `/opt/scalper/src`, crea el entorno virtual e instala el paquete con scikit-learn;
4. copia `config.yaml` a `/opt/scalper/config.yaml` (solo la primera vez) y apunta `data_dir` a `/opt/scalper/data`;
5. instala y arranca dos servicios: `scalper-paper` (recolecta, simula y reentrena) y `scalper-dashboard` (panel en 127.0.0.1:8787).

Si prefieres clonar directo desde el servidor: `sudo bash deploy/install.sh URL_DEL_REPO RAMA`.

## 4. Comprobar que corre

```bash
systemctl status scalper-paper scalper-dashboard     # ambos "active (running)"
journalctl -u scalper-paper -f                       # log en vivo; Ctrl+C para salir
```

En el log deberías ver `discovery: N mercados`, las conexiones `ws0…ws5 conectado`, `sports feed
conectado` y, cada minuto, una línea `estado:` con contadores. Los datos aparecen en
`/opt/scalper/data/`.

Atajo para los comandos del bot en el servidor:

```bash
alias scalper='sudo -u scalper /opt/scalper/venv/bin/scalper -c /opt/scalper/config.yaml'
scalper status        # qué tablas hay y su rango
scalper report        # predicho vs real por señal
scalper retention     # uso de disco y crecimiento
scalper wallets       # ranking de wallets
scalper models        # versiones del modelo aprendido
```

## 5. Ver el panel desde tu computadora

El panel escucha solo en el propio servidor. Se ve por un túnel SSH, que lo cifra y no lo expone:

```bash
ssh -N -L 8787:127.0.0.1:8787 admin@IP_DEL_SERVIDOR
```

Deja esa terminal abierta y abre `http://127.0.0.1:8787` en el navegador. Se actualiza solo.

## 6. Disco

La retención corre sola una vez al día dentro del recolector (`retention.run_hours`). Conserva
3 días de cambios de libro y 14 de instantáneas, borra el resto y compacta cada día cerrado a un
archivo por tabla. Las tablas que alimentan el aprendizaje (cotizaciones, trades, partidos, flujo,
wallets, señales, ledger) no se borran nunca.

```bash
scalper retention              # cuánto ocupa cada tabla y cuánto crece por día
scalper retention --dry-run    # qué borraría y compactaría, sin tocar nada
scalper retention --apply      # hacerlo ahora
df -h /opt/scalper             # espacio libre del disco
```

Si el disco baja de 10 GB libres, reduce `keep_days` en `/opt/scalper/config.yaml` y reinicia con
`sudo systemctl restart scalper-paper`.

## 7. Actualizar el código

```bash
cd ~/scalper-src && git pull
cd polymarket_scalper && sudo bash deploy/install.sh    # reinstala y reinicia los servicios
```

`config.yaml` en `/opt/scalper/` no se sobrescribe: los cambios de configuración se hacen ahí.

## 8. Copias de seguridad

Lo valioso son las tablas pequeñas y el ledger, no los cambios de libro. Desde tu computadora:

```bash
rsync -av --exclude 'book_deltas' --exclude 'book_snapshots' admin@IP:/opt/scalper/data/ ./respaldo-scalper/
```

Con la retención activa eso pesa unos cientos de MB por semana.

## 9. Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `estado:` muestra `libros_validos` muy bajo | mercados sin liquidez a esa hora | normal; sube `discovery.min_volume_24h` si molesta |
| `flow: la página completa era nueva` repetido | el sondeo de trades no alcanza | baja `flow.poll_seconds` a 5 |
| `flow_lag` de varios minutos | la API de datos de Polymarket va con retraso | normal, es su indexador; no afecta al libro |
| el servicio se reinicia en bucle | error de configuración | `journalctl -u scalper-paper -n 100` muestra la traza |
| `sports feed desconectado` cada pocos minutos | red inestable del proveedor | reconecta solo; si persiste, cambia de región |
| el panel no abre | túnel SSH cerrado | vuelve a lanzar el `ssh -N -L …` |

## 10. Qué esperar las primeras semanas

- **Días 1 a 3:** se llena `data/`, se perfilan wallets, los partidos empiezan a verse desde antes del arranque.
- **Semana 1:** `scalper report` empieza a tener decenas de posiciones válidas por señal. Si el PnL válido de alguna señal es positivo de forma consistente, esa es la candidata.
- **Semana 2 a 3:** `scalper train` (automático cada 6 h) tiene ejemplos suficientes; `scalper models` muestra si el modelo le gana a la heurística.
- Solo entonces tiene sentido hablar de la fase 6, el ejecutor con dinero real de tamaño mínimo.

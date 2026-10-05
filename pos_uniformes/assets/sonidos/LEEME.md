# Sonidos para los avisos

Cada archivo de esta carpeta es un sonido que un aviso puede hacer sonar en las
pantallas de la tienda:

    /aviso sonido=risa 🤡 Te veo...

El nombre que se escribe en el comando es el del archivo **sin la extensión y
sin acentos**: `risa.wav` → `sonido=risa`.

- **Formato recomendado: `.wav`.** Suena al instante y no depende de códecs.
  `.mp3` y `.ogg` también se intentan, pero si el kiosko no trae el códec, el
  aviso sale igual y en silencio (nunca se queda sin mostrar por el sonido).
- **Cortos.** El aviso dura 12 h por defecto pero el sonido se oye una vez, al
  aparecer. Algo de 2 a 5 segundos.
- Para ver cuáles hay desde el celular: `/sonidos`.

Los sonidos viajan DENTRO de la app del satélite, así que después de dejar un
archivo aquí hay que correr `scripts\actualizar_pc_principal.bat` para que los
kioskos se lo lleven.

Nada de esta carpeta se sube con música o audio de alguien más sin permiso.

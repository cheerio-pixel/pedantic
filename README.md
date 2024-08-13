
# Pedantic

# Descripcion

Bot de discord que marca errores ortograficos en oraciones.

**Importante**
Este proyecto fue creado y publicado unicamente con el proposito de ser educativo, y de ser practica y ejemplo.

Este proyecto implementa

1. Cliente de HTTP
2. Cliente de Websockets
3. Algoritmo de correccion de Norvig
4. Interfaz minima de la API de Discord

# Instalacion

Usando docker:

> $ poetry export -f requirements.txt > requirements.txt
> $ docker build -t .

Usando poetry:

> $ poetry install

# Ejectuar

Si se quiere ejecutar usando docker:
> $ docker run -it --rm --env-file=.env frairlyn/pedantic:latest

Si se quiere ejecutar usando poetry:

> $ poetry run python main.py

# Configuracion

Las variables de entorno son las siguientes:

```
DISCORD_CLIENT_ID=0000000000000000000
DISCORD_CLIENT_SECRET=ssssssssssssssssssssssssssssssss
DISCORD_CLIENT_TOKEN=tttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttttt

BOT_PREFIX==>
MODEL_PATH=models/crea_formas_ortograficas.txt
```


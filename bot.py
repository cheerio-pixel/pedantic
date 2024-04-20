"""Logica del bot de discord. Monitorea los canales y reenvia los mensajes a la IA."""

__all__ = ["quickstart_bot"]

import json
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4
from pprint import pprint


import discord

from corrector import Corrector, CsvModelLoader, NorvigCorrector
from lib.http import HttpClient, Url
from lib.websocket import WebsocketFactory
from maybe import Maybe
from model import AuthorizedUser, CreateMessage, Message, ReadyEvent

base_api_url = "https://discord.com/api/v10"


def button(msg: str, id: str | None = None) -> dict[str, Any]:
    """Crea un diccionario que representa (en discord) un boton con
    mensaje.

    Su estilo predeterminado es secundario. Para saber mas revisa
    https://discord.com/developers/docs/interactions/message-components#button-object-button-styles

    Parameters
    ----------
    msg: str
        Mensaje dentro del boton.

    Returns
    -------
    dict[str, Any]
        Diccionario que representa el boton.
    """

    return {
        "type": 2,  # Boton
        "style": 2,  # Secundario
        "label": msg,
        "custom_id": id,
    }


def send_msg(
    user: AuthorizedUser,
    channel_id: str,
    msg: str,
    message_id: str | None = None,
    components: list[Any] | None = None,
):
    """Envia un mensaje de parte del usuario.

    Parameters
    ----------
    channelId: str
        Id del canal a donde enviar el mensaje.

    msg: str
        Contenido del mensaje a enviar.

    message_id: str | None
        Id del mensaje a referenciar, si no es None, esto lo enviara como
        una respuesta.

    components: list[Any] | None
        Lista opcional de componentes.
    """
    headers = {
        "Authorization": ["Bot " + user.token],
        "Content-Type": ["application/json"],
    }
    payload: dict[str, Any] = {
        "content": msg,
    }
    if message_id:
        payload["message_reference"] = {"message_id": message_id}
    if components:
        payload["components"] = components
    response = HttpClient.post(
        Url.from_url(base_api_url + f"/channels/{channel_id}/messages"),
        headers,
        json.dumps(payload).encode(),
    )
    if response.status_code not in {200, 204}:
        print(response.status_code)
        pprint(response.body)


def send_interaction_response(payload: dict[str, Any], interaction_id: str, interaction_token: str):
    """Envia una respuesta a evento de Interaction.

    Revisa https://discord.com/developers/docs/interactions/receiving-and-responding#responding-to-an-interaction
    para saber formas de responder a un Interaction

    Parameters
    ----------
    payload: dict[str, Any]
        Un objeto respuesta. Vea https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-response-object para saber mas.

    interaction_id: str
        Id del Interaction.

    interaction_token: str
        Token del interaction. Valido 15 minutos despues de su creacion.
    """
    headers = {
        "Content-Type": ["application/json"],
    }
    response = HttpClient.post(Url.from_url(
        base_api_url + f"/interactions/{interaction_id}/{interaction_token}/callback"
    ), headers, json.dumps(payload).encode())
    if response.status_code != 204:
        print(response.status_code)
        pprint(response.body)

def send_interaction_text_response(msg: str, interaction_id: str, interaction_token: str):
    """Envia un mensaje como respuesta a un evento de Interaction.

    Revisa https://discord.com/developers/docs/interactions/receiving-and-responding#interaction-response-object-messages para mas detalles.

    Parameters
    ----------
    msg: str
        Cuerpo del mensaje.

    interaction_id: str
        Id del Interaction.

    interaction_token: str
        Token del interaction. Valido 15 minutos despues de su creacion.
    """
    payload = {
        "type": 4,
        "data": {
            "content": msg,
        },
    }
    send_interaction_response(payload, interaction_id, interaction_token)

def send_interaction_ack_response(interaction_id: str, interaction_token: str):
    """Envia un PONG como respuesta a un evento Interaction.

    Funciona como un no-operacion (noop) para cuando se recibe un Interaction.

    Parameters
    ----------
    interaction_id: str
        Id del Interaction.

    interaction_token: str
        Token del interaction. Valido 15 minutos despues de su creacion.
    """
    payload = {
        "type": 1
    }
    send_interaction_response(payload, interaction_id, interaction_token)


def delete_message(user: AuthorizedUser, channel_id: str, message_id: str):
    """Borra un mensaje del historial de discord bajo la autorizacion de un
    usuario o bot.

    Parameters
    ----------
    channel_id: str
        Id del canal de discord.

    message_id: str
        Id del mensaje de discord.
    """
    headers  = {
        "Authorization" : ["Bot " + user.token]
    }
    response = HttpClient.delete(
        Url.from_url(
            base_api_url + f"/channels/{channel_id}/messages/{message_id}",
        ),
        headers
    )
    if response.status_code != 204:
        print(channel_id, message_id)
        print(response.status_code)
        pprint(response.body)


# Definicion de la logica del bot


class BotConfig(Protocol):
    """Protocolo de configuracion del bot.

    Define el estado de un bot y las formas de personalizarlo.
    """
    @property
    def is_being_pedantic(self) -> bool:
        """Revisa si el bot esta activado o no.

        Returns
        -------
        bool
            True si esta activado, False en caso contrario.
        """
        ...

    @is_being_pedantic.setter
    def is_being_pedantic(self, value: bool) -> None:
        """Setter de esta propiedad.
        """
        ...

    @property
    def prefix(self) -> str:
        """Caracter o string que el bot intercepta como llamadas a
        comandos.

        Returns
        -------
        str
            El prefijo configurado.
        """
        ...


class BotInteractionsStore(Protocol):
    """Protocolo de las acciones que necesita un bot para guardar
    informacion de las interacciones.
    """
    def get_interaction(self, interaction_id: str) -> Maybe[str]:
        """Obten la palabra de una interaccion.

        Parameters
        ----------
        interaction_id: str
            Id de la interaccion que fue evocada.

        Returns
        -------
        Maybe[str]
            Palabra que esta asociada a esta interaction, si existe.
        """
        ...

    def save_interaction(self, interaction_id: str, word: str):
        """Guarda la informacion necesario para poder guardar la palabra
        indicada si el usuario asi lo quiere.

        Parameters
        ----------
        interaction_id: str
            Id del objeto que evoca la interaccion.

        word: str
            La palabra asociada a esta interaccion.
        """
        ...


class InMemoryBotInteractionsStore:
    """Implementacion del protocolo `BotInteractionsStore` para operaciones en la memoria.
    """
    def __init__(self):
        self.store: dict[str, str] = {}

    def get_interaction(self, interaction_id: str) -> Maybe[str]:
        return Maybe(self.store.get(interaction_id))

    def save_interaction(self, interaction_id: str, word: str):
        self.store[interaction_id] = word


# Go-esque implementation without compile-time assurance
class InMemoryBotConfig:
    """Implementacion del protocolo `BotConfig` para configuracion en la memoria.
    """
    def __init__(self, prefix: str, pedantic: bool = True):
        self._pedantic = pedantic
        self._prefix = prefix

    @property
    def is_being_pedantic(self) -> bool:
        return self._pedantic

    @is_being_pedantic.setter
    def is_being_pedantic(self, value: bool) -> None:
        self._pedantic = value

    @property
    def prefix(self) -> str:
        return self._prefix


class Bot(discord.DiscordGatewayClient):
    """Bot de Pedantic. Se encarga de leer todos los mensajes de discord y
    quejarse por errores tipograficos.

    Attributes
    ----------
    _bot_config: BotConfig
        La configuracion del bot.

    _corrector: Corrector
        La logica interna del bot.

    _interaction_store: BotInteractionsStore
        El encargado de ayudar a coordinar los eventos de la api Interaction.
    """
    def __init__(
        self,
        *,
        bot_config: BotConfig,
        corrector: Corrector,
        interaction_store: BotInteractionsStore,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._bot_config = bot_config
        self._corrector = corrector
        self._interaction_store = interaction_store

        # Decoradores
        self.on_message = self.register(
            discord.GatewayEvents.MESSAGE_CREATE, lambda data: CreateMessage(**data)
        )(self.on_message)
        self.on_ready = self.register(discord.GatewayEvents.READY)(self.on_ready)
        self.on_interaction = self.register(discord.GatewayEvents.INTERACTION_CREATE)(
            self.on_interaction
        )

    def prefixed_with(self, content: str, command: str) -> bool:
        """Revisa si el mensaje es un comando de bot con dicho nombre.

        Parameters
        ----------
        content: str
            El contenido del mensaje.

        command: str
            El comando que esperamos.

        Returns
        -------
        bool
            Verdadero si es ese comando, falso en caso contrario.
        """
        return content == self._bot_config.prefix + command

    def show_status(self, user: AuthorizedUser, message: CreateMessage):
        """Envia un mensaje con el estado del bot en el canal de discord
        que activo este evento.

        Parameters
        ----------
        user: AuthorizedUser
            El usuario que enviara este mensaje.

        message: CreateMessage
            El mensaje que incio este evento.
        """
        reply = "Activado" if self._bot_config.is_being_pedantic else "Desactivado"
        send_msg(user, message.channel_id, reply, message.id)

    def register_new_word(self, word: str, user: AuthorizedUser, interaction_message: Any):
        """Registra una nueva palabra en el diccionario y avisa del cambio por discord.

        Parameters
        ----------
        word: str
            La palabra a añadir.

        user: AuthorizedUser
            El usuario que avisa del cambio en el diccionario.

        interaction_message: Any
            En evento que inicio esta accion.

        """

        Maybe.do(
            Maybe.progn(lambda: self._corrector.add_word(word),
                        lambda: send_interaction_text_response(f"Se agrego {word} al diccionario.",
                                                               interaction_id, interaction_token),
                        lambda: delete_message(user, channel_id, message_id))
        for message in Maybe(interaction_message.get("message"))
        for channel_id in Maybe(message.get("channel_id"))
        for message_id in Maybe(message.get("id"))
        for interaction_token in Maybe(interaction_message.get("token"))
        for interaction_id in Maybe(interaction_message.get("id"))
        )

    def on_interaction(self, user: AuthorizedUser, message: Any):
        """Manejador del evento INTERACTION_CREATE.
        """

        operation = Maybe.do(
            # or True, forzara a esta expresion a evaluarse a un valor
            # valido, de esa forma nosotros podemos desampacarlo y saber si
            # la operacion si se ejecuto.
            self.register_new_word(word, user, message) or True
            for data in Maybe(message.get("data"))
            for custom_id in Maybe(data.get("custom_id"))
            for word in self._interaction_store.get_interaction(custom_id)
        ).value

        if operation is None:
            Maybe.do(
                send_interaction_ack_response(interaction_id, interaction_token)
                for interaction_token in Maybe(message.get("token"))
                for interaction_id in Maybe(message.get("id"))
            )

    def on_ready(self, user: AuthorizedUser, message: ReadyEvent):
        """Manejador del evento READY.
        """
        print("Sesion iniciada como " + user.username)

    def on_ayuda(self, user: AuthorizedUser, message: Message):
        """Responde al evento de Ayuda.

        Parameters
        ----------
        user: AuthorizedUser
            El bot o usuario que esta ejecutando esta accion.

        message: Message
            El mensaje que inicio este evento.
        """
        send_msg(
            user,
            message.channel_id,
            """Prefijo: =>
=>activar: Empieza ser pedantico.
=>desactivar: Calla al pedantico""",
            )

    def on_message(self, user: AuthorizedUser, message: CreateMessage):
        """Manejador del evento MESSAGE_CREATE.

        Este manejador se encarga de analizar los comandos y redigirir las
        palabras al corrector.
        """
        if message.author.id == user.id:
            return

        if len(message.content) <= 1:
            return

        if self.prefixed_with(message.content, "activar"):
            self._bot_config.is_being_pedantic = True
            self.show_status(user, message)
            return

        if self.prefixed_with(message.content, "desactivar"):
            self._bot_config.is_being_pedantic = False
            self.show_status(user, message)
            return

        if self.prefixed_with(message.content, "ayuda"):
            self.on_ayuda(user, message)
            return

        if not self._bot_config.is_being_pedantic:
            return

        for word in message.content.replace(",", "").split(" "):
            corrections = self._corrector.spell_check(word)
            if corrections and corrections[0] != word:
                message_reply = f"Un error tipografico en la palabra *{word}*, ¿quisiste decir *{corrections[0]}*?"
                message_reply += f"\nEscribe *{self._bot_config.prefix}ayuda* para ver mas opciones."
                interaction_id = str(uuid4())
                to_send_button = button(
                    "Agrega la palabra al diccionario.", interaction_id
                )
                self._interaction_store.save_interaction(interaction_id, word)
                send_msg(
                    user,
                    message.channel_id,
                    message_reply,
                    message.id,
                    [{"type": 1, "components": [to_send_button]}],
                )
                return


# Inicializacion del bot


def quickstart_bot():
    """Empieza el servidor de discord.

    NOTA: Bloquea el hilo actual.
    """

    from dotenv import load_dotenv
    import os

    load_dotenv()

    # Carga las variables de entornooks
    DISCORD_CLIENT_TOKEN: str = os.environ.get("DISCORD_CLIENT_TOKEN") or ""
    if not DISCORD_CLIENT_TOKEN:
        raise OSError(
            "Variable de entorno DISCORD_CLIENT_TOKEN no fue encontrada en el archivo .env"
        )
    model_path = os.environ.get("MODEL_PATH") or ""
    if not model_path:
        raise OSError(
            "Variable de entorno MODEL_PATH no fue encontrada en el archivo .env"
        )
    model_path = Path(model_path)

    PREFIX = os.environ.get("BOT_PREFIX") or "!"

    # Logica para el API REST

    host = "gateway.discord.gg"
    route = "/?v=9&encoding=json"
    port = 443

    factory = WebsocketFactory(route, host, port)
    # Activa tres cosas, Primero que se puedan ver los mensajes, segundo
    # que pueda ver los mensajes de un servidor y por ultimo los dms (hacia
    # la apliacion). En si no necesito activar MESSAGE_CONTENT, pero aqui
    # hago explicito que configure el cliente para tener este intent
    # privilegiado, y que lo necesitas.
    intents = (
        discord.GatewayIntents.MESSAGE_CONTENT
        | discord.GatewayIntents.GUILD_MESSAGES
        | discord.GatewayIntents.DIRECT_MESSAGES
    )

    bot_config = InMemoryBotConfig(PREFIX)
    loader = CsvModelLoader(model_path)
    model = loader.get_model()
    corrector = NorvigCorrector(model, loader)
    interaction_store = InMemoryBotInteractionsStore()

    bot = Bot(
        bot_config=bot_config,
        corrector=corrector,
        interaction_store=interaction_store,
        factory=factory,
        token=DISCORD_CLIENT_TOKEN,
        intents=intents,
    )

    bot.run()

import json
import struct
import sys
import threading
import time
from typing import Any, Callable, TypeVar

from lib.websocket import Websocket, WebsocketFactory
from maybe import Maybe
from model import AuthorizedUser, ReadyEvent


T = TypeVar("T")

class GatewayOpcode:
    """Codigos que declaran el tipo de dato que sera enviado en una
    websocket.
    """

    Dispatch = 0
    """Client Action: Receive

    An event was dispatched
    """
    Heartbeat = 1
    """Client Action: Send/Receive

    Fired periodically by the client to keep the connection alive.
    """
    Identify = 2
    Presence = 3
    Voice_State = 5
    Resume = 6
    Reconnect = 7
    Request_Guild_Members = 8
    Invalid_Session = 9
    Hello = 10
    Heartbeat_ACK = 11

class GatewayEvents:
    """lista no exahustiva de los eventos que puede mandar la Gateway API
    de discord.
    """

    READY = "READY"
    # Existen otros eventos, los cuales conforman las operacione CRUD del
    # evento mensaje y sus versiones en acciones masivas, pero eso conlleva
    # extra logica que puedo circumventar
    MESSAGE_CREATE = "MESSAGE_CREATE"
    INTERACTION_CREATE = "INTERACTION_CREATE"


class GatewayIntents:
    """Bit flags de los persmisos de la GatewayAPI.
    """
    GUILDS = 1 << 0
    GUILD_MEMBERS = 1 << 1
    GUILD_EMOJIS_AND_STICKERS = 1 << 3
    GUILD_INTEGRATIONS = 1 << 4
    GUILD_WEBHOOKS = 1 << 5
    GUILD_INVITES = 1 << 6
    GUILD_VOICE_STATES = 1 << 7
    GUILD_PRESENCES = 1 << 8
    GUILD_MESSAGES = 1 << 9
    GUILD_MESSAGE_REACTIONS = 1 << 10
    GUILD_MESSAGE_TYPING = 1 << 11
    DIRECT_MESSAGES = 1 << 12
    DIRECT_MESSAGE_REACTIONS = 1 << 13
    DIRECT_MESSAGE_TYPING = 1 << 14
    MESSAGE_CONTENT = 1 << 15
    GUILD_SCHEDULED_EVENTS = 1 << 16
    AUTO_MODERATION_CONFIGURATION = 1 << 20
    AUTO_MODERATION_EXECUTION = 1 << 21


class HeartbeatTimer:
    def __init__(self):
        self.init_time = time.perf_counter()
        self.last_time = time.perf_counter()

    def start(self):
        self.init_time = time.perf_counter()

    def stop(self) -> float:
        self.last_time = time.perf_counter()
        return self.last_time -  self.init_time

class DiscordGatewayClient:
    def __init__(self, factory: WebsocketFactory, token: str, intents: int = GatewayIntents.MESSAGE_CONTENT):
        self.factory = factory
        self.token = token
        self.intents = intents
        self.session_id = None
        self.resume_gateway_url = None
        self.heartbeat_interval = None
        self.heartbeat_thread = None
        self.heartbeat_time = HeartbeatTimer()
        self.last_sequence = None
        self.handlers: dict[str, tuple[Callable[[AuthorizedUser, Any], None], Callable[[Any], Any] | None]] = {}
        # Declaramos una funcion vacia para evitar tener que chequear por None
        self.handler_ready_event: Callable[[AuthorizedUser, ReadyEvent], None] = lambda x, y: None
        self.client: AuthorizedUser | None = None

    # Un decorador es azucar sintactica para la operacion:
    # def func():
    #     return 1
    # def decorador(function):
    #     def inner():
    #         return function() + 1
    #     return inner
    # func = decorador(func)
    # Ahora func devuelve 2 en vez de 1.
    # Como se puede ver, se envuelve la funciona en otra funcion y se
    # modifica su comportamiento. Este concepto es similar a los advices de
    # emacs lisp o los triggers de SQL.
    def register(self, event: str, data_transformer: Callable[[Any], T] | None = None) -> Callable:
        """Decorador para registrar funciones como manejadores de eventos.

        Parameters
        ----------
        event: str
            El nombre del evento a subscribirse, solo se puede asignar uno
            a cada manejador.

        data_transformer: Callable[[Any], T] | None
            Una funcion que toma los datos que se pasaran al manejador y
            los transformara a un objeto.

        Notes
        -----
        El evento READY es especial, este mismo ya recibe el objeto evento
        Ready desreailizado (como un objeto ReadyEvent)
        """
        def inner_function(function: Callable[[AuthorizedUser, T | ReadyEvent], None] ) -> Callable:
            if event == GatewayEvents.READY:
                self.handler_ready_event = function
            else:
                self.handlers[event] = (function, data_transformer)
            return function
        return inner_function

    def pull_message(self, ws: Websocket) -> Maybe[Any]:
        try:
            message = ws.receive_messages()
            return message.map(json.loads)
        except UnicodeDecodeError:
            message.map(lambda x: (str(struct.unpack("!H", x[:2])[0]) + " " + x[2:].decode())).peek(print)
            return Maybe(None)

    def run(self):
        ws, _ = self.factory.handshake()
        with ws:
            # Primero saca el mensaje de inicio
            for data in self.pull_message(ws):
                self.hello(ws, data)

            self.identify(ws)
            self.start_heartbeat_handler(ws)
            while True:
                payload = self.pull_message(ws).value
                if not payload:
                    # TODO: Handle disconnect
                    # TODO: Handle resume
                    # TODO: Handle rate limit
                    # TODO: ¿Mejor redirige los opcodes al cliente?
                    break

                event_type = payload.get("t")
                opcode = payload.get("op")
                data = payload.get("d")
                seq = payload.get("s")

                if seq:
                    self.last_sequence = seq

                if opcode == GatewayOpcode.Heartbeat_ACK:
                    self.acknowledge_heartbeat()

                if opcode == GatewayOpcode.Dispatch:
                    self.handle_event(event_type, data)

    def hello(self, ws: Websocket, data: Any):
        if data:
            self.heartbeat_interval = data["d"]["heartbeat_interval"] / 1000.0
            self.send_heartbeat(ws)

    def start_heartbeat_handler(self, ws: Websocket):
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop, args=(ws,))
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()

    def heartbeat_loop(self, ws: Websocket):
        while True:
            time.sleep(self.heartbeat_interval or 0)
            self.send_heartbeat(ws, self.last_sequence)

    def send_heartbeat(self, ws: Websocket, data = None):
        payload = {
            "op": GatewayOpcode.Heartbeat,
            "d": data
        }
        ws.send_message(json.dumps(payload))
        self.heartbeat_time.start()

    def handle_event(self, event_type: str, event_data: Any):
        if event_type == GatewayEvents.READY:
            event_unserialized = ReadyEvent(**event_data)
            self.session_id = event_unserialized.session_id
            self.client = AuthorizedUser(self.token, **event_unserialized.user.__dict__)
            # Necesitamos copiar el objeto para evitar bugs casos en los
            # que el manejador modifica el objeto, ya que se pasa una
            # referencia.
            self.handler_ready_event(self.client, ReadyEvent(**event_unserialized.__dict__))
            return

        if not self.client:
            raise ValueError("Cliente nulo cuando no deberia de ser")

        for (handler, transformer) in Maybe(self.handlers.get(event_type)):
            data_to_handle = event_data
            if transformer is not None:
                data_to_handle = transformer(data_to_handle)

            handler(self.client, data_to_handle)

            break # Este break es necesario para asegurarse de que el
            # bloque en else solo se ejecute si el for loop no se ejecuto
        else:
            print("Evento " + event_type + " sin manejador.")

    def acknowledge_heartbeat(self):
        result = self.heartbeat_time.stop()
        if result >= 10:
            print("Hubo un restraso de " + str(result) + " segundos desde que se envio el ultimo Heartbeat")

    def identify(self, ws: Websocket):
        payload = {
            "op": 2,
            "d": {
                "token": self.token,
                "intents": self.intents,  # Intents to receive message events
                "properties": {
                    "$os": sys.platform,
                    "$browser": "my_library",
                    "$device": "my_library"
                }
            }
        }
        ws.send_message(json.dumps(payload))

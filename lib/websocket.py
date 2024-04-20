import socket
import ssl
import base64
import random
import struct
from typing import Callable

from maybe import Maybe

ssl_context = ssl.create_default_context(
    ssl.Purpose.SERVER_AUTH
)

ssl_context.verify_mode = ssl.CERT_REQUIRED
ssl_context.check_hostname = True
ssl_context.load_default_certs()



class HandshakeFailure(Exception):
    """Ocurrio un error al establecer el protocolo websocket."""
    pass


class UnknownOpcode(Exception):
    """Se ha encontrado un Opcode que no se reconoce."""
    pass

class UnprocesableOpcode(Exception):
    """El websocket no ha tiene la capacidad de procesar este Opcode
    """
    pass

StatusCode = {
    1000: "Finalizacion normal",
    1001: "Se fue, sea el servidor o el navegador.",
    1002: "Error de protocolo",
    1003: "El punto final rechaza los datos recibidos debido a un tipo de dato no aceptable.",
    1004: "Reservado para definición futura.",
    1005: "Valor reservado indicando ausencia de un código de estado en un marco de control Close.",
    1006: "Valor reservado indicando cierre anormal de la conexión sin envío de marco de control Close.",
    1007: "El punto final rechaza los datos inconsistentes con el tipo del mensaje recibido.",
    1008: "El punto final rechaza un mensaje por violar su política.",
    1009: "El punto final rechaza un mensaje demasiado grande para procesar.",
    1010: "El cliente cierra la conexión porque esperaba extensiones no proporcionadas por el servidor.",
    1011: "El servidor cierra la conexión debido a una condición inesperada que impide cumplir la solicitud.",
    1015: "Valor reservado indicando fallo en el handshake TLS durante el cierre de la conexión."
}
"""Codigos de estado definidos en RFC6455.

https://datatracker.ietf.org/doc/html/rfc6455#section-7.4.1
"""

class Frame:
    def __init__(self, fin: bool, rsv1: bool, rsv2: bool, rsv3: bool, opcode: int, payload: bytes):
        self.fin = fin
        self.rsv1 = rsv1
        self.rsv2 = rsv2
        self.rsv3 = rsv3
        self.opcode = opcode
        self.payload = payload
        if not WebsocketOpcode.is_opcode(opcode):
            raise UnknownOpcode(opcode)


    def serialize(self, masked: bool) -> bytes:
        length = len(self.payload)

        output = bytearray()

        head1 = 0b00000000
        if self.fin:
            head1 |= 0b10000000
        if self.rsv1:
            head1 |= 0b01000000
        if self.rsv2:
            head1 |= 0b00100000
        if self.rsv3:
            head1 |= 0b00010000

        head1 |= self.opcode

        extended_length: None | bytes = None
        head2 = 0b00000000
        # Handle the payload length encoding
        if length <= 125:
            head2 |= length
        elif length <= 0xFFFF:
            head2 |= 126
            extended_length = struct.pack("!H", length)
        else:
            head2 |= 127
            extended_length = struct.pack("!Q", length)

        if masked:
            # Enciende el 8 bit
            head2 |= 0b10000000

        output.append(head1)
        output.append(head2)
        if extended_length:
            output.extend(extended_length)

        if masked:
            # Genera un numero de 32 bits
            # De red, un numero de 32 bits sin signo
            mask = struct.pack('!I', random.getrandbits(32))
            output.extend(mask)
            output.extend(bytearray(self.payload[i] ^ mask[i % 4] for i in range(length)))
        else:
            output.extend(self.payload)

        return output

    @classmethod
    def read_from(cls, read: Callable[[int], bytes]) -> Maybe["Frame"]:
        # Si el servidor envia algo se vera asi el primer byte (invertido,
        # como si fuese 987 cuando deberia ser 789)
        # 0 000 0000
        # El primer bit indica si este es el frame final
        # Los tres siguientes son bits reservados (RSV ?) para ser
        # intepretados en una extension del protocolo websocket. Se supone
        # que tengo que fallar en caso de no poder interpetarlos pero no se.
        # Los ultimos 4 bits son los opcode. O sea, dictan como se tienen
        # que interpertar los bits del payload.
        # Algunos opcodes han sido definidos en `WebsocketOpcode`

        # El segundo byte se ve asi
        # 0 0000000
        # El primer bit indica el payload esta enmascarada. Se proveera
        # justo despues de la longitud del payload (ya sea extendida o no)
        # en 32 bits (4 bytes)
        # Los otros 7 bits contienen la longitud del payload
        # Si la longitud es igual a 126 los siguientes 16 bits (2 bytes) indican la
        # longitud extendida del payload
        # Si en otro caso es 127, los siguientes 64 (8 bytes) bits indican
        # la longitud extendida del payload

        header: bytes = read(2)
        if not header:
            return Maybe(None)

        fin: bool = True if header[0] & 0b10000000 else False
        rsv1: bool = True if header[0] & 0b01000000 else False
        rsv2: bool = True if header[0] & 0b00100000 else False
        rsv3: bool = True if header[0] & 0b00010000 else False


        # Del primer byte del header, saca los primeros 4 digitos, los
        # cuales son el opcode.
        # El operador and (&) de bits hara esto
        # 10101010 &
        # 00001111 ->
        # 00001010
        # Sacando asi un numero entre 15 y 0.
        opcode: int = header[0] & 0x00001111
        # El opcode es un operational code, dentro de lo establecido
        # (depende del contexto) dice como se interpretan los siguientes
        # datos.

        # Obten los primeros 7 bytes
        payload_length = header[1] & 0b01111111

        if payload_length == 126:
            # Los siguientes bytes componen un numero de 16 bits, el modulo
            # struct nos permite reinterpretar bytes a otros datos, en este
            # caso le pasamos ! que es para la endianidad de red. La
            # endianidad se refiere al orden en el que se leen los bytes,
            # de forma que little endian es leyendo desde el byte menor
            # (imaginemos 123, seria 3 por que 1 es 100, mienstras que 3 es
            # 3) al mayor, y big endian lo contraior, desde el mayor al
            # menor. ! network usa big-endian. Y H se refiere a unsigned
            # short, o sea entero sin signo de 2 bytes (16 bits), de 0
            # hasta 65535
            payload_length = struct.unpack("!H", read(2))[0]
        elif payload_length == 127:
            # En este caso es lo mismo, pero Q es unsigned long long, o sea
            # entero sin signo de 8 bytes (64 bits), de 0 hasta 18446744073709551615
            payload_length = struct.unpack("!Q", read(8))[0]

        # Como esto es unicamente para un cliente, por el RFC6455 Seccion
        # 5.1, el servidor no mandara mascaras, pero por completud tendre
        # esto
        is_masked = header[1] & 0b10000000

        if is_masked:
            # Los siguentes 4 bytes despues de la longitud son de la
            # mascara.
            # ¿Que es la mascara?
            # En este caso es una secuencia de 4 bytes (32 bits) que
            # enmascaran los dato, ¿Como? Usan el algoritmo presentado mas
            # adelante y envuelven los datos para que no sean faciles de
            # leer, ¿Por que? En esta parte no lo tengo claro, pero es para
            # que intermediarios (una proxy, por ejemplo) no puedan predecir
            # (hacer cache) el formato de los datos. ¿Por que esto causa
            # problemas? Tambien quiero saberlo, pero la secuencia de casos
            # que un hacker debe de dar son largos, y carezco la madurez de
            # poder entender.
            mask = read(4)

        payload = read(payload_length)

        if is_masked:
            # El algoritmo especificado en el RFC6455.
            # La parte `mask[i % 4] ^ payload[i]`
            # Hace la operacion XOR por cada byte de la mascara (ciclando
            # cada 4 iteraciones, ya que son solo 4 bytes como se pidieron
            # anteriormente), con un byte en el payload
            # El XOR funciona como una suma modulo 2. O sea que
            # 1 ^ 1 -> 0
            # 1 ^ 0 -> 1
            # 0 ^ 0 -> 0
            payload = bytes([mask[i % 4] ^ payload[i] for i in range(payload_length)])

        return Maybe(cls(
            fin,
            rsv1,
            rsv2,
            rsv3,
            opcode,
            payload
        ))

class WebsocketOpcode:
    # https://datatracker.ietf.org/doc/html/rfc6455#section-11.8
    CONTINUATION_FRAME = 0x0
    TEXT_FRAME = 0x1
    BINARY_FRAME = 0x2
    CONNECTION_CLOSE_FRAME = 0x8
    PING_FRAME = 0x9
    PONG_FRAME = 0x10

    @classmethod
    def is_opcode(cls, opcode: int):
        # __dict__ retorna todos los attributes de un objeto, en nuetro
        # caso un clase, la cual serian todos sus campos
        return opcode in cls.__dict__.values()


class Websocket:
    """Implementacion de un cliente de WebSocket."""

    def __init__(self, inner_socket: socket.socket):
        self.inner_socket = inner_socket

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.inner_socket.close()

    def send_message(self, message: str, masked: bool = True):

        frame_bytes = Frame(True, False, False, False, WebsocketOpcode.TEXT_FRAME, message.encode("utf-8")).serialize(masked)

        self.inner_socket.send(frame_bytes)

    def receive_messages(self) -> Maybe[bytes]:
        result: bytearray = bytearray()
        while True:
            frame: Frame | None = Frame.read_from(self.inner_socket.recv).value
            if not frame:
                return Maybe(None)

            if frame.opcode in (WebsocketOpcode.TEXT_FRAME,
                                WebsocketOpcode.BINARY_FRAME,
                                WebsocketOpcode.CONTINUATION_FRAME):
                result.extend(frame.payload)

            if frame.opcode == WebsocketOpcode.CONNECTION_CLOSE_FRAME:
                self.inner_socket.close()
                (status_code,) = struct.unpack("!H", frame.payload)
                print(StatusCode.get(status_code))
                return Maybe(None)

            if frame.opcode == WebsocketOpcode.PING_FRAME:
                # Para completud, en la seccion 5.5.2 del RFC6455, se
                # especifica que se tiene que mandar devuelta el contenido
                # del ping.
                self.send_pong(frame.payload)
                result.extend(frame.payload)

            if frame.opcode == WebsocketOpcode.PONG_FRAME:
                # No implementado, pero existe el caso en que discord me
                # envie un PONG, asi que simplemente logearemos
                print("PONG!", frame.payload)
                result.extend(frame.payload)

            if frame.fin:
                return Maybe(result)

            if not result:
                raise UnprocesableOpcode(frame.opcode)

    def send_pong(self, payload: bytes):
        # Create a PONG frame and send it over the socket
        pong_frame = Frame(True, False, False, False, WebsocketOpcode.PONG_FRAME, payload)
        self.inner_socket.send(pong_frame.serialize(masked=False))

class WebsocketFactory:
    """Creador de Websockets.

    Attributes
    ----------
    route: str
        String con formato de '/camino/al/recurso'

    host: str
        Nombre del dominio. Ejemplo con https://google.com/search => google.com

    port: int
        El puerto del socket.

    retries: int = 5
        El numero de reintentos antes de hacer un Timeout
    """

    def __init__(self, route: str, host: str, port: int, retries: int = 5, timeout: int = 5):
        self.route = route
        self.host = host
        self.port = port
        # En caso de no poder conectarse, cuantas veces deberia de volver a
        # reintentar conectarse
        self.retries = retries

    def handshake(self) -> tuple[Websocket, str]:
        """Inicializa el proceso de cambio de protocolos.

        Returns
        -------
        tuple[Websocket, str]
            Primer elemento es el envoltorio sobre el socket.
            Segundo elemento es la repuesta dada por el servidor.
        """
        # Idea general
        # ------------
        # Un socket es la abstracion de un punto en la red el cual puede
        # recibir y enviar datos.
        #
        # Familia de direcciones
        # ----------------------
        # Son una especificion del tipo de direcciones que el socket desea
        # intercambiar comunicarse, en nuestro caso AF_INET hace referencia
        # a las direcciones IPv4. O sea, este socket usara el protocolo
        # IPv4 para el routing (saber como resolver el host), ¿por que?
        # casi todos lo usan, o sea que es los mas seguro en termino que
        # tanto puede fallar.
        #
        # Tipo de Socket
        # --------------
        # SOCK_STREAM en este caso es que la conecion sera TCP. O sea que
        # se establecera una conexion de dos-vias, persistente y con un
        # stream de datos. Cuando digo en un stream de datos es que los
        # envirara en como una secuencia de bytes y de paso el protocolo
        # TCP se asegurara de que sea en orden y no se pierdan paquetes de
        # datos, persistente es que la conexion no se cerrara despues de
        # enviar el mensaje.
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 80 es el puerto del protocolo http, el cual envia el payload sin
        # ningun tipo de encripcion (o sea, texto simple y claro), el
        # puerto 443 es el de https. La seguridad viene con la capa TLS,
        # que usa una encriptacion de llaves asimetrica.
        #
        # El flujo va mas o menos asi:
        # 1. El cliente envia un mensaje de "hola", en la que detalla la
        # version de TLS, el conjunto de algoritmos a utilizar para
        # asegurar la conexion y una string aleatoria de bytes.
        # 2. El servidor responde con un certificado SSL, el conjunto de
        # algoritmos a utilizar para asegurar la conexion que el servidor
        # eligio y una string aleatoria de bytes
        # 3. El cliente verifica el certificado SSL del servidor con la
        # autoridad que lo genero. Esto confirma que el servidor es quien
        # dice que es.
        # 4. El cliente genera otra string aleatoria de bytes llamada
        # secreto premaster. El la encripta con la llave publica que esta
        # en el certificado SSL y el servidor recibe esta string.
        # 5. El servidor des-enscripta el secreto premaster y usa la string
        # aleatoria que el servidor y el cliente mandaron previamente para
        # generar el secreto maestro.
        # 6. El cliente tambien genera el secreto maestro, este tiene que
        # obligatoriamente ser igual al del servidor y sera utilizado como
        # la llave de la sesion actual.
        # 7. El cliente envia un mensaje de "termine" encriptado con el
        # secreto maestro.
        # 8. El servidor envia un mensaje de "termine" encriptado con el
        # secreto maestro.
        # 9. Se ha establecido una conexion segura que se continuara usando
        # el secreto maestro para la encriptacion.
        # NOTA: El secreto maestro es una llave simetrica, o sea, se usa
        # para encriptar y desencriptar mensajes.
        #
        # Llaves asimetricas
        # ------------------
        # Hay dos llaves, la publica y la privada. Comunmente la publica es
        # usada para encriptar y la privda para desencriptar, de forma que
        # se manda la publica al cliente para que este proteja medio de
        # comunicacion.
        #
        # El flujo de datos va algo asi
        # Cliente <-> Clave publica <=> Servidor
        # De forma que se intercambian las llaves publicas y despues se
        # empiezan a enviar mensajes.
        if self.port == 443:
            # No tengo ni idea de cual seria el mejor, iremos con el que
            # siempre pueden cambiar pero no me hace pensar mucho.
            s = ssl_context.wrap_socket(s, server_hostname=self.host)

        retry = True
        retries = 0
        while retry:
            try:
                s.connect((self.host, self.port))
                retry = False
            except socket.timeout:
                if retries > self.retries:
                    retry = False
                    raise socket.timeout

        # Clave secreta. Usada por el servidor para dar a entender que esto
        # es un cliente de websockets y que el servidor puede manejarlo
        # Principalmente es para rechazar HTTP requests que por acciente
        # (¿como?, algun dia tendre un ejemplo) cambian el protocolo a
        # websocket. Es una confirmacion especial y unica del estandar de
        # este protocolo.
        key = base64.b64encode(bytes(str(random.randint(0, 10**16)), "utf-8"))

        handshake_request = (
            f"GET {self.route} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        s.sendall(handshake_request.encode())

        ws = Websocket(s)

        response: bytes | str = b""
        # b"\r\n\r\n" es carriage return y line feed, dos veces.
        # \n es line feed (siguiente linea). O sea no volvemos al inicio de
        # la linea. De forma que hacemos un \r carriage return (vuevle al
        # inicio). Si uno piensa en terminos de impresora, es como ir a la
        # siguente linea en la impresion y irse a la izquierda.

        # Por defecto, cuando haces \n en un programa de terminal u otro
        # que haga parse, se añade un \r de forma automatica (si es
        # necesario). Pero aqui aparece ya que trabjamos de forma cruda, de
        # bajo nivel y mas importante, para soportar cosas hechas hace 30
        # años.
        while b"\r\n\r\n" not in response:
            # Recive en pedazos de 4096 bytes. No aseguro que el parseo sea
            # correcto ya que encaja perfectamente con la respuesta de
            # discord antes de los siguientes bytes que son el evento Hello
            # (opcode 10)
            response += s.recv(4096)

        response = response.decode()

        # No estamos haciendo un cliente de http, no veo necesario tener
        # que parsear la respuesta.
        if "101 Switching Protocols" not in response:
            raise HandshakeFailure(
                "Ocurrio un error en el handshake con el host "
                + self.host
                + " y puerto "
                + str(self.port)
            )
        return ws, response

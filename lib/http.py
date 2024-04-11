import json
import re
import socket
import ssl
from typing import Any


class MalformedUrlError(Exception):
    """Al momento de analizar la cadena de texto, se encontro que esta no
    tiene el formato correcto.
    """
    pass

class InvalidHttpMethod(Exception):
    """Se introdujo un verbo de http no valido.
    """
    pass

class PrematureSocketClosure(Exception):
    """El medio de comunicacion se cerro antes de que se pudiese completar
    la operacion.
    """
    pass

class HttpMethod:
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
    PUT = "PUT"

    @classmethod
    def is_http_method(cls, method: str):
        return method in cls.__dict__.values()


class Url:
    def __init__(self, scheme: str, domain: str, route: str, port: int | None, query_params: dict[str, Any]):
        self.scheme = scheme
        self.domain = domain
        self.route = route
        self.port = port
        self.query_params = query_params

    def get_route_for_send(self):
        """Devuelve la ruta con sus parametros añadidos al final.
        """
        return (self.route or "/") + "&".join(map(lambda x:  str(x[0]) + "=" + str(x[1]), self.query_params.items()))

    @classmethod
    def from_url(cls, url: str):

        # Grupo 1: Esquema
        # Grupo 2: Dominio
        # Grupo 3: Puerto
        # Grupo 4: Ruta
        # Grupo 5: Parametros de consulta

        # ^ Empieza desde el inicio de la string
        # + hace match con uno o mas de la expresion previa
        # ? Hace match con cero o uno de la expresion previa
        # \ Sirve para escapara caracteres especiales (como los anteriores)
        # y usarlos para hacer match.
        # [] Representa una clase de caracteres, todo lo que esta ahi hace
        # match de uno, o sea si es uno de los caracteres de ahi.
        # ([\w+.-]+) Grupo de captura, captura todo lo que sea un caracter,
        # signo de mas, punto o signo de menos
        # Una string normal hace match con sigo misma, o sea :// hace match
        # con eso mismo
        pattern = r'^([\w+.-]+)://([\w.-]+)(?::(\d+))?(/?[\w\-\./\?=%&]+)?(\?[\w\-\./\?=%&]+)?'

        match = re.match(pattern, url)

        if match:
            query_params = {}
            if match.group(5):
                query_string = match.group(5)
                for param in query_string.split("&"):
                    key, value = param.split("=")
                    query_params[key] = value
            domain = match.group(2)
            if not domain:
                raise MalformedUrlError("El dominio es obligatoro")
            return cls(
                match.group(1),
                domain,
                match.group(4),
                int(match.group(3)) if match.group(3) else None,
                query_params
            )
        else:
            print(url)
            raise MalformedUrlError()

class HttpResponse:
    """Respuesta de HTTP.

    Attributes
    ----------
    headers: dict[str, list[str]]
        Encabezados de la respuesta.

    status_code: int
        Codigo HTTP del estado de la respuesta.
    body: str
        Cuerpo de la respuesta, si lo tiene.
    """

    def __init__(self, headers: dict[str, list[str]], status_code: int, body: str = ""):
        self.headers = headers
        self.status_code = status_code
        self.body = body

    def json(self) -> Any | None:
        """Devuelve el cuerpo de la respuesta como json.
        """
        # Codigo 204: No Content, como no hay nada no es necesario parsear nada.
        return None if self.status_code == 204 else json.loads(self.body)

    @classmethod
    def parse(cls, raw_response: str) -> "HttpResponse":
        """Lee una Response devuelta por un servidor y la convierte en un
        objeto HttpResponse

        Parameters
        ----------
        raw_response: str
            La respuesta en su formato sin procesar, directamente salida
            del servidor.
        """
        headers, body = raw_response.split("\r\n\r\n", 1)

        # Parse headers
        headers_dict = {}
        for line in headers.split("\r\n")[1:]:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if headers_dict.get(key):
                 headers_dict[key].append(value)
            else:
                headers_dict[key] = [value]

        status_line = headers.split("\r\n", 1)[0]
        _, status_code_str, _ = status_line.split(" ", 2)
        status_code = int(status_code_str)

        return cls(headers_dict, status_code, body.strip())



class HttpRequest:
    """
    """
    def __init__(self, method: str, url: Url, headers: dict[str, list[str]] = {}, data: bytes | None=None):

        if not HttpMethod.is_http_method(method):
            raise InvalidHttpMethod(method)

        self.method = method
        self.url = url
        self.headers = headers

        self.data = data

    def serialize(self) -> bytes:
        """Convierte el objeto actual a su version en bytes.

        Returns
        -------
        bytes:
            Una string de bytes en encoding UTF-8 que puede ser mandada
            como Request.
        """
        raw_request = f"{self.method} {self.url.get_route_for_send()} HTTP/1.1\r\n"

        # Asegura que el Host existe, ya que la version 1.1 del protocolo
        # lo requiere.
        self.headers["Host"] = [self.url.domain]

        for header, value in self.headers.items():
            for v in value:
                raw_request += f"{header}: {v}\r\n"

        if self.data:
            raw_request += f"Content-Length: {len(self.data)}\r\n"
        else:
            raw_request += "Content-Length: 0\r\n"

        raw_request += "\r\n"

        raw_request = raw_request.encode(encoding="utf-8")
        if self.data:
            raw_request += self.data

        return raw_request

class HttpClient:
    """Un Cliente de HTTP simple.
    """
    @classmethod
    def get(cls, url: Url, headers: dict[str, list[str]] = {}):
        return cls.request(HttpRequest(HttpMethod.GET, url, headers))

    @classmethod
    def post(cls, url: Url, headers: dict[str, list[str]] = {}, data: bytes | None = None) -> HttpResponse:
        return cls.request(HttpRequest(HttpMethod.POST, url, headers, data))

    @classmethod
    def delete(cls, url: Url, headers: dict[str, list[str]] = {}, data: bytes | None = None) -> HttpResponse:
        return cls.request(HttpRequest(HttpMethod.DELETE, url, headers, data))

    @classmethod
    def put(cls, url: Url, headers: dict[str, list[str]] = {}, data: bytes | None = None) -> HttpResponse:
        return cls.request(HttpRequest(HttpMethod.PUT, url, headers, data))

    @classmethod
    def request(cls, request_object: HttpRequest) -> HttpResponse:
        """Ejecuta una Request en contra la url especificada.
        """

        url: Url = request_object.url
        port = url.port
        if not url.port:
            if url.scheme == "http":
                port = 80 # Puerto por defecto en http
            if url.scheme == "https":
                port = 443 # Puerto por defecto en https

        request_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if url.scheme == "https":
            request_socket = ssl.create_default_context().wrap_socket(request_socket, server_hostname=url.domain)

        with request_socket as s:
            request: bytes = request_object.serialize()
            s.connect((url.domain, port))
            s.sendall(request)
            raw_response: bytearray = bytearray()

            # Esto indica si el header Transfer-Encoding es chunked. Para
            # asi tratar los datos entrantes de una forma especial.
            is_transfer_chunked = False
            # A veces todos los datos se reciben de una, en otras se divide
            # en pedazos, de forma que necesitamos una forma de señalar
            # cuando no pedir mas
            is_body_complete = False

            buffer_size = 4096

            while True:
                chunk = s.recv(buffer_size)

                if not chunk:
                    # El socket se desconecto
                    raise PrematureSocketClosure("En request: " + request.decode())

                raw_response.extend(chunk)

                no_content = (str(204) in raw_response.decode().split("\r\n", 1)[0]
                              and "\r\n\r\n".encode() in raw_response)

                if no_content:
                    return HttpResponse.parse(raw_response.decode())

                if not is_transfer_chunked:
                    if b"Content-Length:" in raw_response:
                        content_length_match = re.search(rb"Content-Length: (\d+)", raw_response)
                        if content_length_match and b"\r\n\r\n" in raw_response:
                            content_length = int(content_length_match.group(1))
                            if len(raw_response.split(b"\r\n\r\n", 1)[1]) >= content_length:
                                is_body_complete = True

                if not is_body_complete and not is_transfer_chunked:
                    if b"Transfer-Encoding: chunked" in raw_response:
                        is_transfer_chunked = True

                if is_transfer_chunked and raw_response.endswith(b"0\r\n\r\n"):
                    is_body_complete = True

                if is_body_complete:
                    if is_transfer_chunked:
                        # [a-fA-F0-9] para hexadecimal, ya que bajo esta
                        # opcion el tamaño es mandado en ese formato.
                        # [a-f] hace match a todo caracter entre a y f, osea abcdef
                        # Los mismo para sus versiones en mayuscula y los numeros
                        return HttpResponse.parse(re.sub(r"\r\n[a-fA-F0-9]+", "", raw_response.decode()))
                    return HttpResponse.parse(raw_response.decode())

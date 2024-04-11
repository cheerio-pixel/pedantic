"""Definicion del tipo monadico Maybe.
"""

from typing import Callable, Generic, Iterable, Iterator, Self, TypeVar

# Declaracion de los tipos genericos T y U

T = TypeVar("T")
U = TypeVar("U")


class Maybe(Generic[T]):
    """Tipo monadico importado de haskell.

    Representa un tipo de dato que tal vez no contenga nada.

    Attributes
    ----------
    value: None | T
        Valor interno de este objeto.

    Examples
    --------

    >>> assoc: dict[str, int] = {'a': 1, 'b': 2, 'c': 3}
    >>> tal_vez = Maybe(assoc.get('d'))
    >>> tal_vez = (
        tal_vez.map(lambda x: x + 1)
               .flat_map(lambda x: Maybe(assoc.get('a') + x)
                         if assoc.get('a')
                         else Maybe(None))
    )
    >>> assert tal_vez.value == None
    """

    def __init__(self, value: None | T):
        self.value: None | T = value

    def map(self, func: Callable[[T], U]) -> "Maybe[U]":
        """Aplica una funcion al valor de este objeto, si existe.

        Parameters
        ----------
        func: Callable[[T], U]
            La funcion a aplicar.

        Returns
        -------
        Maybe[U]
            Una nueva instancia de la clase Maybe pero con el tipo del
            resultado.

        See Also
        --------
        flat_map : Aplica una funcion que retorna un Maybe[U]
        """
        if self.value is not None:
            return Maybe(func(self.value))
        return Maybe(None)

    def flat_map(self, func: Callable[[T], "Maybe[U]"]) -> "Maybe[U]":
        """Aplica una funcion que retorna un Maybe.

        Parameters
        ----------
        func: Callable[[T], Maybe[U]]
            Funcion que sera aplicada en el valor interno

        Returns
        -------
        Maybe[U]
            Una nueva instancia de la clase Maybe pero con el tipo del
            resultado.
        """
        if self.value is not None:
            return func(self.value)
        return Maybe(None)

    def peek(self, func: Callable[[T], None]) -> Self:
        """Applica una funcion sobre el valor interno, no espera que retorne un valor.

        Parameters
        ----------
        func: Callable[[T], None]
            Funcion que se aplicara al valor interno

        args: list[Any]
            Argumentos que se pasaran a la funcion func

        kwargs: dict[str, Any]
            Argumentos de llave-valor que se pasaran a la funcion func

        Returns
        -------
        Self:
            Esta instancia de Maybe
        """
        if self.value is not None:
            func(self.value)
        return self

    # Abusemos del lenguaje
    def __iter__(self) -> Iterator[T]:
        """Permite iterar sobre el valor interno si existe."""
        if self.value is not None:
            yield self.value

    @classmethod
    def do(cls, iterable: Iterable):
        """Des-empaca el valor dentor de una iterable como un Maybe. Se
        supone que debe de ser utilizado con una comprension de listas de
        Maybe's

        Parameters
        ----------
        iterable: Iterable
            Iterable a extraer.

        Returns
        -------
        Maybe:
            Tal vez un valor
        """

        for value in iterable:
            return cls(value)
        return cls(None)

    # Esta funcion no deberia de estar aqui, pero como es de cosas de
    # programacion funcional, se queda.
    @classmethod
    def progn(cls, *args: Callable):
        """Ejecuta mutiples funciones de forma serial.

        Parameters
        ----------
        args: list[Callable]
            Lista de funciones

        Returns
        -------
        Any:
            El resultado de la ultima funcion.
        """
        result = None
        for arg in args:
            result = arg()
        return result

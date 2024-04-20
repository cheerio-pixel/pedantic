"""Logica del corrector de palabras."""

import re
from typing import Protocol

from pathlib import Path
import csv

from dotenv import dotenv_values

from maybe import Maybe

config = dotenv_values(".env")

# Clases de modelo


class WordStatistics:
    """Coleccion de palabras. Contiene funciones que actuan sobre esta
    colecion para ofrecer informacion estadistica.
    """

    def __init__(self, words: dict[str, int]):
        self.words = words
        self.letters = list(set("".join(words.keys())))
        self._size = None

    @property
    def size(self) -> int:
        """Tamño del conjunto de datos.

        No es lo mismo que la cantidad de las palabras
        """
        if not self._size:
            self._size = sum(self.words.values())
        return self._size

    def get_freq_abs(self, word: str) -> Maybe[int]:
        return Maybe(self.words.get(word))

    def get_freq_rel(self, word: str) -> Maybe[float]:
        return self.get_freq_abs(word).map(lambda x: x/self.size)

    def add_word(self, word: str):
        if self.words.get(word) is not None:
            self.words[word] += 1
        else:
            self.words[word] = 1


class Corrector(Protocol):
    def spell_check(self, word: str) -> list[str]: ...
    def add_word(self, word: str): ...


class ModelLoader(Protocol):
    """Protocolo para definir un cargador de modelo de estadisticas de palabras"""

    def get_model(self) -> WordStatistics:
        """
        Obtiene el modelo de estadisticas de palabras.

        Returns
        -------
        WordStatistics
            Instancia de WordStatistics que contiene las estadisticas de palabras cargadas
        """
        ...

class ModelUnloader(Protocol):
    def save_model(self, word_statistics: WordStatistics): ...

class NorvigCorrector:
    """Corrector de palabras basado en el algoritmo de correccion de Norvig"""
    def __init__(self, word_statistics: WordStatistics, saver: ModelUnloader):
        """
        Inicializa el corrector con las estadisticas de palabras

        Parameters
        ----------
        word_statistics : WordStatistics
            Estadisticas de palabras utilizadas para la correccion

        saver: ModelUnloader
            Encargado de guardar el modelo de lenguaje.
        """
        self.word_statistics = word_statistics
        self.saver = saver

    def add_word(self, word: str):
        """Añade una palabra al diccionario.

        Parameters
        ----------
        word: str
            Palabra a añadir.
        """
        self.word_statistics.add_word(word)
        self.saver.save_model(self.word_statistics)

    def edits1(self, word: str):
        """
        Genera las ediciones 1 de la palabra a la vez

        Parameters
        ----------
        word : str
            Palabra de la cual se generaran las ediciones

        Returns
        -------
        set
            Conjunto que contiene todas las ediciones a una distancia de edicion de 1 de la palabra
        """

        # Genera una lista de tuplas de sub-palabras de la palabra `word`
        # las cuales se dividen en pedazos. el + 1 es por que el slicing
        # parara en i, lo cual no incluira el final de la lista si solo se toma la longitud
        # Ejemplo: word = sazon
        # splits = [("", "sazon"), ("s", "azon"), ("sa", "zon"), ("saz", "on"), ("sazo", "n"), ("sazon", "")]
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]

        # Elimina una palabra. Hace esto saltandose una letra del lado
        # derecho de las divisiones anterior y concatenando con el lado derecho
        deletes = [L + R[1:] for L, R in splits if R]
        # Transpone dos letras que estan adayacentes entre si.
        # Usa el mismo truco que el anterior
        transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
        replaces = [L + c + R[1:] for L, R in splits if R for c in self.word_statistics.letters]
        inserts = [L + c + R for L, R in splits for c in self.word_statistics.letters]
        return set(deletes + transposes + replaces + inserts)

    def edits2(self, word):
        "All edits that are two edits away from `word`."
        return (e2 for e1 in self.edits1(word) for e2 in self.edits1(e1))

    def candidates(self, word):
        "Generate possible spelling corrections for word."
        return (
            self.known([word])
            or self.known(self.edits1(word))
            or self.known(self.edits2(word))
            or [word]
        )

    def known(self, words):
        "The subset of `words` that appear in the dictionary of WORDS."
        return set(w for w in words if w in self.word_statistics.words)

    def spell_check(self, word: str) -> list[str]:
        return [max(self.candidates(word), key=lambda x: self.word_statistics.get_freq_rel(x).value or -1)]


class CsvModelLoader:
    def __init__(self, model_path: str | Path):
        self.model_path = model_path

    def only_words(self, word):
        return (
            Maybe(re.search(r"\w+", word)).map(lambda x: x.group()).value
            and word not in "1234567890"
        )

    def get_model(self) -> WordStatistics:
        with open(self.model_path, encoding="utf8") as model_file:
            # Este conjunto de datos usa la comilla como character
            model_reader = csv.reader(model_file, delimiter="\t", quotechar=None)
            model_reader = filter(lambda line: self.only_words(line[0]), model_reader)
            # Salta el encabezado
            next(model_reader)
            return WordStatistics(
                {line[0]: int(line[1]) for line in model_reader}
            )

    def save_model(self, word_statistics: WordStatistics):
        header = [
            "Palabras", "Frecuencias"
        ]
        with open(self.model_path, mode="w", encoding="utf8") as model_file:
            model_writer = csv.writer(model_file, delimiter="\t", quotechar=None)
            model_writer.writerow(header)
            model_writer.writerows([k, v] for k, v in word_statistics.words.items())

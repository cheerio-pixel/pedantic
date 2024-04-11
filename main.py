"""Bot de discord el cual corrige erorers tipograficos.
"""


# Al momento de importar codigo de otro script, este sera ejecutado. Al
# momento de ejecutar un script de python, python asigna variables valores
# a variable especiales. Es convencion que todas que son de este estilo
# esten rodeados de dos barras bajas. __name__ es una de estas y el valor
# asignado el nombre del modulo, pero cuando esta siendo ejecutada de forma
# directa: Por ejemplo, `python main.py` o `python discord.py` esta tendra
# el valor de __main__. De forma que el siguiente bloque solo sera
# ejecutado cuando se corra de forma directa.
if __name__ == "__main__":
    from bot import quickstart_bot

    quickstart_bot()

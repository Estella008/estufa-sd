
import sqlite3
import threading
from datetime import datetime

con = None
trava = threading.Lock()  


def conectar(id_replica):
    global con
    con = sqlite3.connect(f"controlador_{id_replica}.db", check_same_thread=False)
    with trava:
        con.execute("""CREATE TABLE IF NOT EXISTS leituras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cultura TEXT, grandeza TEXT, valor REAL, momento TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS comandos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cultura TEXT, atuador TEXT, ligar INTEGER, motivo TEXT, momento TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS estado_atuadores (
            cultura TEXT, atuador TEXT, ligado INTEGER,
            PRIMARY KEY (cultura, atuador))""")
        con.commit()


def agora():
    return datetime.now().isoformat(timespec="seconds")


def salvar_leitura(cultura, grandeza, valor):
    with trava:
        con.execute("INSERT INTO leituras (cultura, grandeza, valor, momento) VALUES (?, ?, ?, ?)",
                    (cultura, grandeza, valor, agora()))
        con.commit()


def salvar_comando(cultura, atuador, ligar, motivo):
    # guarda no histórico E atualiza o estado atual do atuador
    with trava:
        con.execute("INSERT INTO comandos (cultura, atuador, ligar, motivo, momento) VALUES (?, ?, ?, ?, ?)",
                    (cultura, atuador, int(ligar), motivo, agora()))
        con.execute("INSERT OR REPLACE INTO estado_atuadores VALUES (?, ?, ?)",
                    (cultura, atuador, int(ligar)))
        con.commit()


def ultima_leitura(cultura, grandeza):
    with trava:
        linha = con.execute("SELECT valor FROM leituras WHERE cultura=? AND grandeza=? "
                            "ORDER BY id DESC LIMIT 1", (cultura, grandeza)).fetchone()
    return linha[0] if linha else None


def leituras_atuais(cultura):
    # {grandeza: valor mais recente} de uma cultura
    with trava:
        linhas = con.execute("SELECT grandeza, valor FROM leituras WHERE id IN "
                             "(SELECT MAX(id) FROM leituras WHERE cultura=? GROUP BY grandeza)",
                             (cultura,)).fetchall()
    return {grandeza: valor for grandeza, valor in linhas}


def estado_atual(cultura):
    # {atuador: True/False}
    with trava:
        linhas = con.execute("SELECT atuador, ligado FROM estado_atuadores WHERE cultura=?",
                             (cultura,)).fetchall()
    return {atuador: bool(ligado) for atuador, ligado in linhas}


if __name__ == "__main__":
    conectar(99)
    salvar_leitura("tomate", "temperatura", 30.5)
    salvar_leitura("tomate", "umidade_solo", 55.0)
    salvar_comando("tomate", "ventilacao", True, "temp 30.5")
    print("última temperatura:", ultima_leitura("tomate", "temperatura"))
    print("leituras atuais:", leituras_atuais("tomate"))
    print("estado atual:", estado_atual("tomate"))

import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from pathlib import Path

import grpc
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import estufa_pb2 as pb2
import estufa_pb2_grpc as pb2_grpc
from config import CULTURAS, MODOS, NUM_CONTROLADORES, PORTA_MIDDLEWARE, porta_controlador

PASTA = Path(__file__).parent
app = FastAPI(title="Painel da Estufa")

class Componente:
    def __init__(self, nome, tipo, *args):
        self.nome = nome
        self.tipo = tipo
        self.args = args
        self.processo = None
        self.log = deque(maxlen=12)
        self.invadido = False

    def rodando(self):

        return self.processo is not None and self.processo.poll() is None

    def iniciar(self):
        if self.rodando():
            return
        self.log.clear()
        self.invadido = False
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

        self.processo = subprocess.Popen(
            [sys.executable, "-u", *self.args],
            cwd=PASTA, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )

        threading.Thread(target=self._ler_saida, args=(self.processo,), daemon=True).start()

    def _ler_saida(self, processo):
        for linha in processo.stdout:
            self.log.append(linha.rstrip())

    def parar(self):
        if self.rodando():

            self.processo.kill()
            self.log.append("--- processo derrubado pelo painel ---")

componentes = {}
componentes["middleware"] = Componente("middleware", "middleware", "middleware.py")
for i in range(1, NUM_CONTROLADORES + 1):
    componentes[f"controlador-{i}"] = Componente(f"controlador-{i}", "controlador", "controlador.py", str(i))
for cultura in CULTURAS:
    componentes[f"atuador-{cultura}"] = Componente(f"atuador-{cultura}", "atuador", "atuador.py", cultura)
for cultura in CULTURAS:
    componentes[f"sensor-{cultura}"] = Componente(f"sensor-{cultura}", "sensor", "sensor.py", cultura)

def broker_online():

    try:
        with socket.create_connection(("localhost", 1883), timeout=0.3):
            return True
    except OSError:
        return False

def perguntar_se_e_lider(componente):

    if not componente.rodando():
        return None
    porta = porta_controlador(int(componente.args[1]))
    try:
        with grpc.insecure_channel(f"localhost:{porta}") as canal:
            stub = pb2_grpc.ControladorStub(canal)
            resposta = stub.ObterStatus(pb2.StatusRequest(cultura=CULTURAS[0]), timeout=0.5)
            return resposta.lider
    except grpc.RpcError:
        return None

def buscar(nome):
    if nome not in componentes:
        raise HTTPException(status_code=404, detail=f"componente '{nome}' não existe")
    return componentes[nome]

@app.get("/")
def pagina():
    return FileResponse(PASTA / "painel.html")

def erro_do_middleware(erro):

    if erro.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED, grpc.StatusCode.ABORTED):
        return HTTPException(status_code=503, detail=f"sem resposta do sistema: {erro.details()}")
    return HTTPException(status_code=400, detail=erro.details())

@app.get("/api/estufa")
def estufa():
    culturas = []
    with grpc.insecure_channel(f"localhost:{PORTA_MIDDLEWARE}") as canal:
        stub = pb2_grpc.EstufaStub(canal)
        for cultura in CULTURAS:
            try:
                r = stub.ObterStatus(pb2.StatusRequest(cultura=cultura), timeout=3)
            except grpc.RpcError as erro:
                raise erro_do_middleware(erro)
            culturas.append({
                "cultura": r.cultura,
                "leituras": dict(r.leituras),
                "faixas": {g: [f.minimo, f.maximo] for g, f in r.faixas.items()},
                "atuadores": {n: {"ligado": a.ligado, "modo": a.modo} for n, a in r.atuadores.items()},
                "controlador_id": r.controlador_id,
                "lider": r.lider,
                "votos": r.votos,
                "consultados": r.consultados,
                "divergentes": list(r.divergentes),
            })
    return {"culturas": culturas}

class PedidoModo(BaseModel):
    modo: str

@app.post("/api/estufa/{cultura}/{atuador}")
def definir_modo(cultura: str, atuador: str, pedido: PedidoModo):
    if pedido.modo not in MODOS:
        raise HTTPException(status_code=422, detail=f"modo deve ser um de {MODOS}")
    with grpc.insecure_channel(f"localhost:{PORTA_MIDDLEWARE}") as canal:
        stub = pb2_grpc.EstufaStub(canal)
        try:
            r = stub.DefinirModo(pb2.ModoRequest(cultura=cultura, atuador=atuador, modo=pedido.modo), timeout=5)
        except grpc.RpcError as erro:
            raise erro_do_middleware(erro)
    return {"ok": r.ok, "mensagem": r.mensagem, "confirmacoes": r.confirmacoes}

@app.get("/api/componentes")
def listar():
    lista = []
    for c in componentes.values():
        lista.append({
            "nome": c.nome,
            "tipo": c.tipo,
            "rodando": c.rodando(),
            "lider": perguntar_se_e_lider(c) if c.tipo == "controlador" else None,
            "invadido": c.invadido,
            "log": list(c.log),
        })
    return {"broker": broker_online(), "componentes": lista}

@app.post("/api/componentes/{nome}/iniciar")
def iniciar(nome: str):
    if not broker_online():
        raise HTTPException(status_code=503, detail="broker MQTT fora do ar (Docker Desktop está aberto?)")
    buscar(nome).iniciar()
    return {"ok": True}

@app.post("/api/componentes/{nome}/parar")
def parar(nome: str):
    buscar(nome).parar()
    return {"ok": True}

class PedidoFalha(BaseModel):
    ativa: bool

@app.post("/api/componentes/{nome}/falha")
def injetar_falha(nome: str, pedido: PedidoFalha):

    c = buscar(nome)
    if c.tipo != "controlador" or not c.rodando():
        raise HTTPException(status_code=409, detail="só dá para invadir um controlador que está rodando")
    with grpc.insecure_channel(f"localhost:{porta_controlador(int(c.args[1]))}") as canal:
        try:
            pb2_grpc.ControladorStub(canal).InjetarFalha(pb2.FalhaRequest(ativa=pedido.ativa), timeout=2)
        except grpc.RpcError as erro:
            raise HTTPException(status_code=503, detail=erro.details())
    c.invadido = pedido.ativa
    return {"ok": True}

@app.post("/api/iniciar-tudo")
def iniciar_tudo():
    if not broker_online():
        raise HTTPException(status_code=503, detail="broker MQTT fora do ar (Docker Desktop está aberto?)")

    for tipo, espera in (("controlador", 2), ("middleware", 0.5), ("atuador", 0.5), ("sensor", 0)):
        for c in componentes.values():
            if c.tipo == tipo:
                c.iniciar()
        time.sleep(espera)
    return {"ok": True}

@app.post("/api/parar-tudo")
def parar_tudo():
    for c in componentes.values():
        c.parar()
    return {"ok": True}

if __name__ == "__main__":
    print("subindo o broker MQTT (Docker)...")
    subprocess.run(["docker", "compose", "up", "-d"], cwd=PASTA)
    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8000")).start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
    finally:
        parar_tudo()
        print("painel encerrado, todos os processos foram parados.")
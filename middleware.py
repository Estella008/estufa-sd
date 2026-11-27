
import grpc
import estufa_pb2 as pb2
import estufa_pb2_grpc as pb2_grpc
from config import controladores_validos

TOLERANCIA = 3.0   


LIMITES = {
    "temperatura": (-10, 60),
    "umidade_ar": (0, 100),
    "umidade_solo": (0, 100),
    "luminosidade": (0, 150),
}


def _stub(controlador_id):
    canal = grpc.insecure_channel(f"localhost:{50050 + controlador_id}")
    return pb2_grpc.ControladorStub(canal)


def _plausivel(leituras):
    for grandeza, valor in leituras.items():
        minimo, maximo = LIMITES.get(grandeza, (float("-inf"), float("inf")))
        if not minimo <= valor <= maximo:
            return False
    return True


def _concordam(a, b):
    comuns = set(a) & set(b)
    return all(abs(a[g] - b[g]) <= TOLERANCIA for g in comuns)


def obter_status(cultura):
    
    respostas = []
    for cid in controladores_validos:
        try:
            r = _stub(cid).ObterStatus(pb2.StatusRequest(cultura=cultura), timeout=2)
            respostas.append(r)
        except grpc.RpcError as erro:
            if erro.code() == grpc.StatusCode.NOT_FOUND:
                raise ValueError(erro.details())
            print(f"  [middleware] controlador {cid} não respondeu, ignorando")

    if not respostas:
        raise RuntimeError("nenhum controlador disponível")

    
    validas = []
    for r in respostas:
        if _plausivel(dict(r.leituras)):
            validas.append(r)
        else:
            print(f"  [middleware] ALERTA: controlador {r.controlador_id} enviou valores impossíveis, descartado")
    if not validas:
        raise RuntimeError("nenhuma resposta confiável")

    
    def votos(r):
        return sum(_concordam(dict(r.leituras), dict(o.leituras)) for o in validas)
    
    escolhida = max(validas, key=lambda r: (votos(r), r.lider))

    for r in validas:
        if not _concordam(dict(r.leituras), dict(escolhida.leituras)):
            print(f"  [middleware] ALERTA: controlador {r.controlador_id} diverge da maioria")
    if len(validas) > 1 and votos(escolhida) <= len(validas) // 2:
        print("  [middleware] aviso: não houve maioria clara")
    return escolhida


def acionar(cultura, atuador, modo):
   
    sucesso = False
    mensagem = "nenhum controlador disponível"
    for cid in controladores_validos:
        try:
            r = _stub(cid).AcionarAtuador(
                pb2.AcaoRequest(cultura=cultura, atuador=atuador, modo=modo), timeout=2)
            mensagem = r.mensagem
            if r.sucesso:
                sucesso = True
        except grpc.RpcError:
            print(f"  [middleware] controlador {cid} não respondeu, tentando o próximo")
    return sucesso, mensagem
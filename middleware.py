

from concurrent import futures
import grpc
import estufa_pb2 as pb2
import estufa_pb2_grpc as pb2_grpc
from config import NUM_CONTROLADORES, PORTA_MIDDLEWARE, porta_controlador

TIMEOUT_S = 1.0
TOLERANCIA = 5.0
MAIORIA = NUM_CONTROLADORES // 2 + 1

ERROS_DE_INDISPONIBILIDADE = (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED)

stubs = {
    i: pb2_grpc.ControladorStub(grpc.insecure_channel(f"localhost:{porta_controlador(i)}"))
    for i in range(1, NUM_CONTROLADORES + 1)
}

class ServicoEstufa(pb2_grpc.EstufaServicer):

    def ObterStatus(self, request, context):

        with futures.ThreadPoolExecutor(max_workers=len(stubs)) as executor:
            pedidos = {i: executor.submit(stub.ObterStatus, request, timeout=TIMEOUT_S)
                       for i, stub in stubs.items()}
        respostas = {}
        for i, pedido in pedidos.items():
            try:
                respostas[i] = pedido.result()
            except grpc.RpcError as erro:
                if erro.code() in ERROS_DE_INDISPONIBILIDADE:
                    print(f"controlador {i} não respondeu ({erro.code().name})")
                    continue
                context.abort(erro.code(), erro.details())
        if not respostas:
            context.abort(grpc.StatusCode.UNAVAILABLE, "nenhum controlador respondeu")

        for i, resposta in respostas.items():
            apoiadores = [j for j, outra in respostas.items() if concordam(resposta, outra)]
            if len(apoiadores) >= MAIORIA:
                divergentes = sorted(set(respostas) - set(apoiadores))
                for d in divergentes:
                    print(f"ALERTA: controlador {d} divergiu da maioria em {request.cultura} "
                          f"(invadido ou com erro?) - resposta dele foi IGNORADA")
                return marcar(resposta, len(apoiadores), len(respostas), divergentes)

        if len(respostas) == 1:

            unica = next(iter(respostas.values()))
            return marcar(unica, 1, 1, [])
        context.abort(grpc.StatusCode.ABORTED,
                      f"réplicas {sorted(respostas)} discordam entre si e não há maioria")

    def DefinirModo(self, request, context):

        confirmacoes = 0
        for id_controlador, stub in stubs.items():
            try:
                stub.DefinirModo(request, timeout=TIMEOUT_S)
                confirmacoes += 1
            except grpc.RpcError as erro:
                if erro.code() in ERROS_DE_INDISPONIBILIDADE:
                    print(f"controlador {id_controlador} fora do ar, não recebeu a escrita")
                    continue
                context.abort(erro.code(), erro.details())
        if confirmacoes == 0:
            context.abort(grpc.StatusCode.UNAVAILABLE, "nenhum controlador recebeu o comando")
        print(f"{request.cultura}/{request.atuador} -> '{request.modo}' "
              f"confirmado por {confirmacoes} de {len(stubs)} réplicas")
        return pb2.ModoResponse(ok=True, confirmacoes=confirmacoes,
                                mensagem=f"aplicado em {confirmacoes} de {len(stubs)} réplicas")

def concordam(a, b):

    if set(a.leituras) != set(b.leituras):
        return False
    for g in a.leituras:
        if abs(a.leituras[g] - b.leituras[g]) > TOLERANCIA:
            return False
    for nome in a.atuadores:
        if (a.atuadores[nome].ligado != b.atuadores[nome].ligado or
                a.atuadores[nome].modo != b.atuadores[nome].modo):
            return False
    return True

def marcar(resposta, votos, consultados, divergentes):

    final = pb2.StatusResponse()
    final.CopyFrom(resposta)
    final.votos = votos
    final.consultados = consultados
    final.divergentes.extend(divergentes)
    return final

servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
pb2_grpc.add_EstufaServicer_to_server(ServicoEstufa(), servidor)
servidor.add_insecure_port(f"[::]:{PORTA_MIDDLEWARE}")
servidor.start()
print(f"middleware: servidor gRPC na porta {PORTA_MIDDLEWARE}")
servidor.wait_for_termination()
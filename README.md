# 🌱 Estufa Inteligente — Sistema Distribuído com MQTT e gRPC

Trabalho prático da disciplina de **Sistemas Distribuídos** (Sistemas de Informação – IFMG Ouro Branco).

Simula uma estufa com três culturas (**tomate, alface e couve**) monitoradas por sensores e controladas por atuadores. Os componentes se comunicam por **MQTT** (publish/subscribe) e os clientes acessam o sistema por um **middleware gRPC** que consulta controladores **replicados**, tolerando falhas e detectando réplicas com comportamento divergente.

## ✨ Destaques

- **Replicação com votação por maioria** — o middleware consulta os 3 controladores em paralelo e só aceita a resposta apoiada pela maioria; réplicas que divergem são sinalizadas como possivelmente comprometidas.
- **Eleição de líder** — o controlador de menor ID ativo é o líder, que envia os comandos aos atuadores. Quando ele cai, outro assume.
- **Detecção de falhas** — cada controlador publica presença no MQTT com *Last Will*; quando um processo morre, os demais são avisados automaticamente.
- **Persistência e recuperação** — cada controlador salva seu estado em disco e o recupera ao reiniciar.
- **Injeção de falhas** — é possível simular uma réplica "invadida" e ver o sistema ignorá-la.
- **Painel web** — sobe e derruba cada processo, mostra logs e permite trocar o modo dos atuadores (auto / ligado / desligado).

## 🏗️ Arquitetura

```text
 sensor.py (tomate, alface, couve)            atuador.py (por cultura)
          │  publica leituras                        ▲  recebe comandos
          ▼                                          │
   ┌─────────────────── Broker MQTT (Mosquitto / Docker) ───────────────────┐
          │                                          ▲
          ▼                                          │
   controlador.py 1   controlador.py 2   controlador.py 3   (réplicas, líder = menor ID ativo)
          ▲                 ▲                 ▲
          └──────── gRPC ───┴──────── gRPC ───┘
                            │
                     middleware.py  (votação por maioria)
                            ▲ gRPC
             ┌──────────────┴──────────────┐
         cliente.py (CLI)           painel.py (FastAPI + painel.html)
```

## 🛠️ Tecnologias

- **Python 3.10+**
- **MQTT** com [paho-mqtt](https://pypi.org/project/paho-mqtt/) e broker **Eclipse Mosquitto** (Docker)
- **gRPC / Protocol Buffers** (`estufa.proto`)
- **FastAPI + Uvicorn** para o painel web
- **Docker Compose**

## 🚀 Como executar

Pré-requisitos: Python 3.10+ e Docker.

```bash
git clone https://github.com/Estella008/estufa-sd.git
cd estufa-sd
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Pelo painel (recomendado)

```bash
python painel.py
```

O painel sobe o broker MQTT via Docker e abre `http://localhost:8000`, onde é possível iniciar todos os componentes, derrubar processos individualmente e acompanhar os logs.

### Manualmente

```bash
docker compose up -d                 # broker MQTT na porta 1883
python controlador.py 1              # repita para 2 e 3, cada um em um terminal
python middleware.py
python atuador.py tomate             # repita para alface e couve
python sensor.py tomate              # repita para alface e couve
```

### Cliente de linha de comando

```bash
python cliente.py tomate                       # status da cultura
python cliente.py tomate irrigacao ligado      # muda o modo de um atuador
```

Se alterar o `estufa.proto`, regenere os stubs:

```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. estufa.proto
```

## 📁 Estrutura

| Arquivo | Responsabilidade |
|---|---|
| `config.py` | Culturas, faixas ideais, atuadores e portas |
| `sensor.py` | Simula leituras (temperatura, umidade do ar e do solo, luminosidade) e reage aos atuadores |
| `atuador.py` | Recebe comandos de irrigação, ventilação, aquecimento e iluminação |
| `controlador.py` | Réplica que decide os comandos, elege líder e persiste estado |
| `middleware.py` | Servidor gRPC que agrega as réplicas com votação por maioria |
| `cliente.py` | Cliente gRPC de linha de comando |
| `painel.py` / `painel.html` | Painel web de controle e observação |
| `estufa.proto` | Contrato gRPC |

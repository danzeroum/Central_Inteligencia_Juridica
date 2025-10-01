import json
from uuid import uuid4

import redis

r = redis.Redis(host="localhost", port=6379, db=0)

tarefa = {
    "id_tarefa": str(uuid4()),
    "descricao": "Analisar recurso especial sobre vicio oculto em bens de consumo",
}

r.lpush("fila:jurisprudencia", json.dumps(tarefa))
print(f"Tarefa {tarefa['id_tarefa']} enviada para o agente de jurisprudencia!")

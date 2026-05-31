import json
import logging
import os
import time

import redis

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
INPUT_QUEUE = "fila:jurisprudencia"
OUTPUT_QUEUE = "fila:resultados"


def connect_to_redis():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r.ping()
        logger.info("Conectado ao Redis!")
        return r
    except redis.exceptions.ConnectionError as e:
        logger.error("Nao foi possivel conectar ao Redis. Detalhe: %s", e)
        return None


def processar_tarefa(tarefa: dict):
    # BUGFIX (CRÍTICO-06): removido o ``time.sleep(5)`` bloqueante que apenas
    # simulava "busca intensiva" e travava o worker. A função é leve e rápida.
    logger.info("Recebi a tarefa: %s", tarefa.get("descricao"))
    resultado = {
        "id_tarefa": tarefa.get("id_tarefa"),
        "agente": "jurisprudencia",
        "status": "concluido",
        "dados": f"Analise para '{tarefa.get('descricao')}' concluida (simulacao).",
    }
    logger.info("Tarefa finalizada.")
    return resultado


def main():
    redis_conn = connect_to_redis()
    if not redis_conn:
        return
    logger.info("Aguardando tarefas na fila '%s'...", INPUT_QUEUE)
    while True:
        try:
            _, tarefa_json = redis_conn.brpop(INPUT_QUEUE, timeout=0)
            tarefa = json.loads(tarefa_json)
            resultado = processar_tarefa(tarefa)
            redis_conn.lpush(OUTPUT_QUEUE, json.dumps(resultado))
        except KeyboardInterrupt:  # encerramento limpo do worker
            logger.info("Encerrando worker de jurisprudência.")
            break
        except (redis.exceptions.RedisError, json.JSONDecodeError) as e:
            # BUGFIX (CRÍTICO-06): exceções específicas (antes era genérico),
            # mantendo a resiliência do laço sem mascarar erros inesperados.
            logger.error("Erro ao processar item da fila: %s", e)
            time.sleep(1)


if __name__ == "__main__":
    main()

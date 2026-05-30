// Helper de WebSocket para a fila HITL, com reconexão automática
// (resolve "WS sem orientação/reconexão" da auditoria — H9).
import { wsUrl } from './client.js';

export function connectHitl({ onEvent, onStatus }) {
  let ws = null;
  let closed = false;
  let retry = 0;

  const connect = () => {
    onStatus?.('connecting');
    ws = new WebSocket(wsUrl('/api/v1/hitl/ws'));
    ws.onopen = () => { retry = 0; onStatus?.('connected'); };
    ws.onmessage = (e) => {
      try { onEvent?.(JSON.parse(e.data)); } catch { /* ignora frames inválidos */ }
    };
    ws.onclose = () => {
      onStatus?.('disconnected');
      if (!closed) {
        const delay = Math.min(1000 * 2 ** retry, 15000);
        retry += 1;
        setTimeout(connect, delay);
      }
    };
    ws.onerror = () => ws && ws.close();
  };

  connect();
  return () => { closed = true; ws && ws.close(); };
}

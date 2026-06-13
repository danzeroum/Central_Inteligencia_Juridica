/**
 * useSlots — carrega os slots de módulos ativos do backend e assina SSE
 * para atualizações em tempo real sem rebuild da SPA.
 *
 * Retorna array de slots conforme GET /api/v1/slots.
 * Quando um módulo é toggled via PATCH /api/v1/modules/{id}, o SSE notifica
 * este hook que re-busca os slots atualizados.
 */

import { useEffect, useRef, useState } from 'react';

import { api } from '../api/client.js';

export function useSlots() {
  const [slots, setSlots] = useState([]);
  const esRef = useRef(null);

  const loadSlots = () => {
    api.get('/api/v1/slots')
      .then(data => setSlots(data.slots || []))
      .catch(() => {});
  };

  useEffect(() => {
    loadSlots();

    const es = new EventSource('/api/v1/slots/stream');
    esRef.current = es;

    es.onmessage = (ev) => {
      if (ev.data && !ev.data.startsWith(':')) {
        loadSlots();
      }
    };

    es.onerror = () => {};

    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, []);

  return slots;
}

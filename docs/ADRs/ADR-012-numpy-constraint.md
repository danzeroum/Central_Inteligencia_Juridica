# ADR-012: NumPy Version Constraint for ChromaDB Compatibility

## Status
Aceito (2025-09-30)

## Contexto
Durante os testes finais da Fase 3, identificamos um erro de compatibilidade:

```
AttributeError: `np.float_` was a deprecated alias for the builtin `float`. 
To avoid this error in existing code, use `float` by itself.
```

**Causa**: ChromaDB versões < 0.5.0 utilizam `np.float_`, que foi removido no NumPy 2.0+.

**Descoberta**: Testes passaram em desenvolvimento mas falharam após atualização implícita de NumPy.

## Decisão
Fixar **NumPy < 2.0.0** em `requirements.txt` e `requirements-dev.txt` até que ChromaDB seja atualizado ou substituído.

**Constraint aplicado**: `numpy<2.0.0,>=1.22.0`

## Alternativas Consideradas

### 1. Upgrade ChromaDB para 0.5.0+
**Prós**: Compatível com NumPy 2.0  
**Contras**: ChromaDB 0.5.0 tem breaking changes na API  
**Decisão**: Não adotar agora (requer refactoring em `src/tools/rag_tool.py`)

### 2. Remover ChromaDB Completamente
**Prós**: Simplifica dependências  
**Contras**: Remove capacidade de vector store (opcional mas útil)  
**Decisão**: Não adotar (é uma feature documentada)

### 3. Fixar NumPy < 2.0 (ESCOLHIDO)
**Prós**: 
- Fix imediato sem refactoring
- Mantém todas as features
- NumPy 1.x ainda é amplamente usado

**Contras**: 
- Eventual necessidade de upgrade
- NumPy 2.0 tem melhorias de performance

**Decisão**: Adotar como solução de curto prazo

## Consequências

### Positivas
- ✅ Testes voltam a passar imediatamente
- ✅ Sistema mantém todas as funcionalidades
- ✅ Sem breaking changes no código existente
- ✅ Documentação clara para future upgrades

### Negativas
- ⚠️ Não aproveita melhorias do NumPy 2.0
- ⚠️ Eventual necessidade de upgrade quando ChromaDB suportar

### Mitigações
- Documentar em `CHANGELOG.md` para tracking
- Adicionar TODO em `src/tools/rag_tool.py` para future upgrade
- Monitorar releases do ChromaDB para atualização futura

## Plano de Upgrade Futuro

Quando ChromaDB 0.5.0+ estiver estável:

1. [ ] Testar ChromaDB 0.5.0 em ambiente isolado
2. [ ] Refatorar `src/tools/rag_tool.py` conforme breaking changes
3. [ ] Atualizar constraint de NumPy para `>=2.0.0`
4. [ ] Executar full test suite
5. [ ] Atualizar ADR-012 com status "Superseded"

## Validação

```
# Validar fix
pip install -r requirements-dev.txt
pytest -q

# Verificar versões
pip list | grep -E "(numpy|chromadb)"
# Esperado: numpy 1.26.x, chromadb 0.4.18
```

## Referências
- NumPy 2.0 Migration Guide: https://numpy.org/devdocs/numpy_2_0_migration_guide.html
- ChromaDB Changelog: https://github.com/chroma-core/chroma/releases
- Issue Relacionada: `tests/test_*.py` failures

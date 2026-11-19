"""Adaptador de entrada: CSV UTF-8 separado por ponto e vírgula."""
import csv
import json
import sys

with open(sys.argv[1], encoding='utf-8-sig', newline='') as file:
    reader = csv.DictReader(file, delimiter=';')
    if reader.fieldnames != ['pedido', 'fornecedor', 'email', 'valor']:
        raise SystemExit('Cabeçalho esperado: pedido;fornecedor;email;valor')
    rows = list(reader)
    if not 1 <= len(rows) <= 1000 or any(None in row or None in row.values() for row in rows):
        raise SystemExit('CSV deve ter de 1 a 1000 linhas, todas com quatro colunas.')
    print(json.dumps(rows, ensure_ascii=False))

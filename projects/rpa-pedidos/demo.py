"""Sistema local fictício para exercitar RPA. Python 3.9+, sem dependências."""
import argparse
import json
import re
import sqlite3
import socket
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def validate(data):
    pedido = str(data.get('pedido', '')).strip().upper()
    fornecedor = str(data.get('fornecedor', '')).strip()
    email = str(data.get('email', '')).strip()
    if not re.fullmatch(r'PED-\d{4}', pedido):
        raise ValueError('Pedido deve ter o formato PED-0001.')
    if not 2 <= len(fornecedor) <= 100:
        raise ValueError('Fornecedor deve ter entre 2 e 100 caracteres.')
    if len(email) > 150 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('E-mail inválido.')
    try:
        value = Decimal(str(data.get('valor', '')).strip().replace(',', '.'))
        if not value.is_finite() or not 0 < value <= 1000000 or value != value.quantize(Decimal('.01')):
            raise ValueError('Valor deve ser positivo, até 1 milhão, com até 2 casas decimais.')
    except InvalidOperation as exc:
        raise ValueError('Valor inválido.') from exc
    return pedido, fornecedor, email, int(value * 100)


def register(path, data):
    record = validate(data)
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS pedidos (pedido TEXT PRIMARY KEY, fornecedor TEXT, email TEXT, centavos INTEGER)')
        # A chave única impede duplicatas mesmo se a resposta se perder e houver retentativa.
        previous = db.execute('SELECT pedido, fornecedor, email, centavos FROM pedidos WHERE pedido=?', (record[0],)).fetchone()
        if previous:
            if previous != record:
                raise ValueError('Conflito: este pedido já existe com outros dados. Revisão necessária.')
            return {'status': 'ja_existente', 'pedido': record[0]}
        db.execute('INSERT INTO pedidos VALUES (?,?,?,?)', record)
    return {'status': 'cadastrado', 'pedido': record[0]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, body, kind='application/json'):
        content = (json.dumps(body, ensure_ascii=False) if kind == 'application/json' else body).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', kind + '; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path == '/':
            return self.reply(200, Path(__file__).with_name('portal.html').read_text(), 'text/html')
        if self.path == '/api/health':
            return self.reply(200, {'ok': True})
        self.reply(404, {'erro': 'Página inexistente.'})

    def do_POST(self):
        if self.path != '/api/pedidos':
            return self.reply(404, {'erro': 'Rota inexistente.'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.reply(415, {'erro': 'Envie JSON.'})
        origin = self.headers.get('Origin')
        if origin and origin != f'http://127.0.0.1:{self.server.server_port}':
            return self.reply(403, {'erro': 'Origem inválida.'})
        if self.server.simulate_unavailable:
            return self.reply(503, {'erro': 'Indisponibilidade simulada para testar recuperação.'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 8000:
                raise ValueError('Tamanho inválido.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Objeto JSON esperado.')
            result = register(self.server.db_path, data)
            if self.server.simulate_lost_response:
                self.server.simulate_lost_response = False
                # O sistema salva, mas o navegador não recebe a resposta.
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                self.close_connection = True
                return
            return self.reply(200, result)
        except (ValueError, TypeError) as exc:
            return self.reply(400, {'erro': str(exc)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8770)
    parser.add_argument('--db', default='output/pedidos.sqlite3')
    parser.add_argument('--simulate-lost-response', action='store_true')
    parser.add_argument('--simulate-unavailable', action='store_true')
    args = parser.parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.db_path = args.db
    server.simulate_lost_response = args.simulate_lost_response
    server.simulate_unavailable = args.simulate_unavailable
    print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}'}), flush=True)
    server.serve_forever()

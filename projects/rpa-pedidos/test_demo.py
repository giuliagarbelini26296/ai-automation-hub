import sqlite3
import tempfile
import unittest
from pathlib import Path
from demo import register, validate


class PedidosTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'db.sqlite3'
        self.row = {'pedido': 'PED-0001', 'fornecedor': 'Empresa Fictícia', 'email': 'a@exemplo.example', 'valor': '10,01'}

    def tearDown(self):
        self.tmp.cleanup()

    def test_reexecucao_nao_duplica_pedido(self):
        self.assertEqual(register(self.db, self.row)['status'], 'cadastrado')
        self.assertEqual(register(self.db, self.row)['status'], 'ja_existente')
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*),centavos FROM pedidos').fetchone(), (1, 1001))

    def test_conflito_nao_sobrescreve_dados(self):
        register(self.db, self.row)
        with self.assertRaisesRegex(ValueError, 'Conflito'):
            register(self.db, {**self.row, 'valor': '20'})

    def test_valores_invalidos_e_precisao(self):
        for value in ['-1', '0', 'NaN', 'Infinity', '1.234', 'abc', '1000001']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate({**self.row, 'valor': value})

    def test_identificador_e_email_invalidos(self):
        for changes in [{'pedido': '../../x'}, {'email': 'sem-email'}, {'fornecedor': ''}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate({**self.row, **changes})


if __name__ == '__main__':
    unittest.main()

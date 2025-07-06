import requests
import json

url = "https://sandbox.sicoob.com.br/sicoob/sandbox/cobranca-bancaria/v3/boletos"

payload = json.dumps({
  "dataEmissao": "2018-09-20",
  "nossoNumero": 2588658,
  "seuNumero": "1235512",
  "valor": 156.5,
  "dataVencimento": "2018-09-20",
  "dataLimitePagamento": "2018-09-20",
  "aceite": True,
  "codigoEspecieDocumento": "DM",
  "numeroCliente": 25546454,
  "codigoModalidade": 1,
  "numeroContaCorrente": 75187241,
  "pagador": {
    "numeroCpfCnpj": "98765432185",
    "nome": "Marcelo dos Santos",
    "endereco": "Rua 87 Quadra 1 Lote 1 casa 1",
    "bairro": "Santa Rosa",
    "cidade": "Luziânia",
    "cep": "72320000",
    "uf": "DF",
    "email": "pagador@dominio.com.br"
  },
  "beneficiarioFinal": {
    "numeroCpfCnpj": "98784978699",
    "nome": "Lucas de Lima"
  },
  "mensagensInstrucao": [
    "Teste mensagem"
  ],
  "numeroContratoCobranca": 1,
  "identificacaoBoletoEmpresa": "4562",
  "identificacaoEmissaoBoleto": 1,
  "identificacaoDistribuicaoBoleto": 1,
  "gerarPdf": False,
  "tipoJurosMora": 3,
  "valorJurosMora": 4,
  "dataJurosMora": "2018-09-20",
  "tipoMulta": 0,
  "valorMulta": 5,
  "dataMulta": "2018-09-20",
  "tipoDesconto": 1,
  "dataPrimeiroDesconto": "2018-09-20",
  "valorPrimeiroDesconto": 1,
  "numeroParcela": 1,
  "codigoCadastrarPIX": 1
})
headers = {
  'Content-Type': 'application/json',
  'Authorization': 'Bearer 1301865f-c6bc-38f3-9f49-666dbcfc59c3',
  'Accept': 'application/json',
  'client_id': '9b5e603e428cc477a2841e2683c92d21',
  'User-Agent': 'PostmanRuntime/7.4.1',
  # 'Cookie': '3335c623dfb80f915ea5457e9d5d4421=9b5b7462af495d4f602fe8d773abf45d; TS016f8952=017a3a183bdaaf76925393b75c52c6bf3132dfdb99c4045312a35e5384c4c0e1fff3052c6d1d0111a1632b2a3831f55a16212d8ef7'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)

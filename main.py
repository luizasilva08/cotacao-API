import requests 
from pprint import pprint


menu_moedas = """

=== Opções de Moedas para Consulta ===

Tradicionais:

USD-BRL (Dólar Americano)
EUR-BRL (Euro)
GBP-BRL (Libra Esterlina)
ARS-BRL (Peso Argentino)

Criptomoedas:

BTC-BRL (Bitcoin)
ETH-BRL (Ethereum)

=====================================

"""
print(menu_moedas)

def consultar_moeda(moeda):
    url = f"https://economia.awesomeapi.com.br/json/last/{moeda}"

    resposta = requests.get(url)

    if resposta.status_code == 200:
        print("Requisição feita!")
        pprint(resposta.json())
        return resposta.json()

    elif resposta.status_code == 404:
        print("Aconteceu um erro na sua requisição.")
        erro = resposta.json()
        status = erro["status"]
        codigo = erro["code"]
        mensagem = erro["message"]
        print(f"O status do seu erro foi: {status}")
        print(f"O código do erro foi: {codigo}")
        print(f"Motivo: {mensagem}.")
        return resposta.json()

    else:
        print("Requisição não feita.")


moeda_desejada = str(input("Digite a moeda que deseja consultar (ex: USD-BRL): "))

dados_api = consultar_moeda(moeda_desejada)

#---------------------------------------------- tratamento do json ----------------
if dados_api:
    valor = dados_api [moeda_desejada]["code"]["bid"]
    print("\nRequisição bem-sucedida!")
    print(f"O valor atual de {moeda_desejada} é: ")
    print(f"R$ {float(valor):.2f}")


else:
    print(f"\nErro ao consultar a moeda: {moeda_desejada}.\nVerifique se o formato está correto.")


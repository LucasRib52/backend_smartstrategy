import requests
from collections import Counter

def obter_clima():
    try:
        # Utiliza o formato JSON para obter a previsão completa do dia
        url = 'https://wttr.in/Praia%20Grande?format=j1'
        resposta = requests.get(url)
        if resposta.status_code == 200:
            dados = resposta.json()
            if "weather" in dados and len(dados["weather"]) > 0:
                # Seleciona a previsão do dia atual
                weather_today = dados["weather"][0]
                hourly_forecasts = weather_today.get("hourly", [])
                condicoes = []
                for hour in hourly_forecasts:
                    # Cada hora possui uma lista com a descrição do clima
                    if "weatherDesc" in hour and len(hour["weatherDesc"]) > 0:
                        condicoes.append(hour["weatherDesc"][0]["value"])
                if condicoes:
                    # Conta qual condição aparece com maior frequência ao longo do dia
                    condicao_mais_comum = Counter(condicoes).most_common(1)[0][0]
                    condicao_lower = condicao_mais_comum.lower()
                    # Mapeia a condição para estados conhecidos
                    if "sunny" in condicao_lower or "clear" in condicao_lower:
                        return "Ensolarado"
                    elif "cloud" in condicao_lower or "overcast" in condicao_lower:
                        return "Nublado"
                    elif "rain" in condicao_lower or "showers" in condicao_lower:
                        return "Chuvoso"
                    elif "thunderstorm" in condicao_lower or "storm" in condicao_lower:
                        return "Tempestade"
                    elif "snow" in condicao_lower:
                        return "Nevando"
                    else:
                        return "Desconhecido"
                else:
                    return "Desconhecido"
            else:
                return "Desconhecido"
        else:
            return "Desconhecido"
    except Exception:
        return "Erro"

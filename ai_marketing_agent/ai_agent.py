"""
AI Marketing Agent - Agente de IA para processamento de dados de marketing
"""

import os
import json
import base64
import logging
import unicodedata
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from io import BytesIO

import openai
import pandas as pd
import pdfplumber
from PIL import Image
import magic
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

class AIMarketingAgent:
    """Agente de IA para processamento de dados de marketing"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None) or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key é obrigatória")
        
        # Verifica compatibilidade entre versões da lib openai
        if hasattr(openai, 'OpenAI'):
            # Versão >= 1.0 (novo client)
            self.client = openai.OpenAI(api_key=self.api_key)
            self._use_new_client = True
        else:
            # Versão < 1.0 (client antigo)
            openai.api_key = self.api_key
            self.client = openai
            self._use_new_client = False

        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        
        # Campos esperados nos dados de marketing
        self.expected_fields = [
            'data', 'campaign_name', 'platform', 'clicks', 
            'impressions', 'cost', 'conversions'
        ]
    
    def process_file(self, file_path: str, user_id: int, empresa_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Processa um arquivo e extrai dados de marketing usando IA
        
        Args:
            file_path: Caminho para o arquivo
            user_id: ID do usuário que fez o upload
            empresa_id: ID da empresa (opcional)
            
        Returns:
            Dict com resultados do processamento
        """
        try:
            # Detecta o tipo do arquivo
            mime_type = magic.from_file(file_path, mime=True)
            
            # Processa baseado no tipo
            if self._is_spreadsheet(mime_type):
                data = self._process_spreadsheet(file_path)
            elif self._is_pdf(mime_type):
                data = self._process_pdf(file_path)
            elif self._is_image(mime_type):
                data = self._process_image(file_path)
            else:
                raise ValueError(f"Tipo de arquivo não suportado: {mime_type}")
            
            # Valida e limpa os dados
            cleaned_data = self._validate_and_clean_data(data)
            
            return {
                'success': True,
                'data': cleaned_data,
                'records_count': len(cleaned_data),
                'file_type': mime_type
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar arquivo {file_path}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': [],
                'records_count': 0
            }
    
    def _is_spreadsheet(self, mime_type: str) -> bool:
        """Verifica se é uma planilha"""
        return mime_type in [
            'text/csv',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
    
    def _is_pdf(self, mime_type: str) -> bool:
        """Verifica se é um PDF"""
        return mime_type == 'application/pdf'
    
    def _is_image(self, mime_type: str) -> bool:
        """Verifica se é uma imagem"""
        return mime_type.startswith('image/')
    
    def _process_spreadsheet(self, file_path: str) -> List[Dict[str, Any]]:
        """Processa planilhas (CSV, Excel)"""
        try:
            # Lê a planilha
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            # -------------- Normaliza nomes das colunas --------------
            def _normalize_column(col_name: str) -> str:
                """Remove acentos, espaços extras e converte para snake_case minúsculo"""
                if not isinstance(col_name, str):
                    col_name = str(col_name)
                # Remove acentos
                col_name = unicodedata.normalize('NFKD', col_name).encode('ASCII', 'ignore').decode('ASCII')
                # Espaços para underscore e lower
                return col_name.lower().strip().replace(' ', '_')

            df.columns = [_normalize_column(col) for col in df.columns]
            
            # Mapeia colunas comuns para os campos esperados
            column_mapping = {
                'data': 'data',
                'date': 'data',
                'dia': 'data',
                'campanha': 'campaign_name',
                'campaign': 'campaign_name',
                'campaign_name': 'campaign_name',
                'nome_campanha': 'campaign_name',
                'plataforma': 'platform',
                'platform': 'platform',
                'cliques': 'clicks',
                'clicks': 'clicks',
                'impressoes': 'impressions',
                'impressions': 'impressions',
                'impressões': 'impressions',
                'custo': 'cost',
                'cost': 'cost',
                'gasto': 'cost',
                'conversoes': 'conversions',
                'conversions': 'conversions',
                'conv': 'conversions',
                # Sinônimos adicionais
                'leads': 'clicks',
                'investimento_realizado': 'cost',
                'investimento': 'cost',
                'invest': 'cost',
                'cpc_med': 'cpc',
                'custo_medio': 'cpc'
            }
            
            # Renomeia colunas
            df = df.rename(columns=column_mapping)
            
            # Remove linhas de totais ou vazias de campanha
            if 'campaign_name' in df.columns:
                mask_total = df['campaign_name'].astype(str).str.strip().str.lower().str.startswith(('total', 'conta', 'pesquisa'))
                df = df[~mask_total]
                df = df[df['campaign_name'].notna() & (df['campaign_name'].astype(str).str.strip() != '')]
            
            # Decide se precisa de enriquecimento da IA
            basic_cols = {'data', 'campaign_name'}
            numeric_cols = {'clicks', 'impressions', 'cost', 'conversions'}
            has_basic = basic_cols.issubset(set(df.columns))
            has_metric = any(col in df.columns for col in numeric_cols)

            records = df.to_dict('records')

            if has_basic and has_metric:
                # Já possui colunas essenciais – não precisa IA
                return records

            # Caso contrário, usa IA para enriquecer linha a linha
            processed_records = []
            for record in records:
                processed = self._enhance_record_with_ai(record)
                if processed:
                    processed_records.append(processed)

            return processed_records
            
        except Exception as e:
            logger.error(f"Erro ao processar planilha {file_path}: {str(e)}")
            raise
    
    def _process_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """Processa PDFs usando OCR e IA"""
        try:
            # Extrai texto do PDF
            with pdfplumber.open(file_path) as pdf:
                text_content = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_content += text + "\n"
            
            # Usa IA para extrair dados estruturados
            prompt = self._create_extraction_prompt(text_content[:8000])  # Limita tamanho
            return self._call_openai_for_extraction(prompt)
            
        except Exception as e:
            logger.error(f"Erro ao processar PDF {file_path}: {str(e)}")
            raise
    
    def _process_image(self, file_path: str) -> List[Dict[str, Any]]:
        """Processa imagens usando Vision API"""
        try:
            # Prepara a imagem para a API
            with Image.open(file_path) as img:
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            # Cria prompt para extração
            prompt = self._create_image_extraction_prompt()
            
            # Chama OpenAI com visão
            return self._call_openai_for_extraction(prompt, image_base64=img_base64)
            
        except Exception as e:
            logger.error(f"Erro ao processar imagem {file_path}: {str(e)}")
            raise
    
    def _enhance_record_with_ai(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Usa IA para melhorar/enriquecer um registro"""
        try:
            # Converte registro para texto
            record_text = json.dumps(record, ensure_ascii=False, default=str)
            
            prompt = f"""
            Analise este registro de marketing e retorne um JSON melhorado com os seguintes campos:
            - data: data no formato YYYY-MM-DD
            - campaign_name: nome da campanha
            - platform: plataforma (google, facebook, instagram, tiktok, linkedin, other)
            - clicks: número de cliques (inteiro)
            - impressions: número de impressões (inteiro)
            - cost: custo em reais (decimal)
            - conversions: número de conversões (inteiro)
            
            Registro original: {record_text}
            
            Retorne apenas o JSON válido:
            """
            
            content = self._chat_completion([
                {"role": "system", "content": "Você é um assistente especializado em dados de marketing digital. Sempre retorne JSON válido."},
                {"role": "user", "content": prompt}
            ], max_tokens=500)
            logger.debug(f"[AI_ENHANCE] Resposta bruta: {content}")

            enhanced_record = self._safe_json_extract(content)
            if enhanced_record is None:
                logger.warning(f"Não foi possível parsear JSON da resposta: {content}")
                return record
            return enhanced_record
                
        except Exception as e:
            logger.error(f"Erro ao melhorar registro com IA: {str(e)}")
            return record
    
    def _create_extraction_prompt(self, text_content: str) -> str:
        """Cria prompt para extração de dados de texto"""
        return f"""
        Extraia dados de marketing digital do seguinte texto. Retorne um array JSON com objetos contendo:
        - data: data no formato YYYY-MM-DD
        - campaign_name: nome da campanha
        - platform: plataforma (google, facebook, instagram, tiktok, linkedin, other)
        - clicks: número de cliques
        - impressions: número de impressões
        - cost: custo em reais
        - conversions: número de conversões
        
        Texto para análise:
        {text_content}
        
        Retorne apenas o array JSON válido:
        """
    
    def _create_image_extraction_prompt(self) -> str:
        """Cria prompt para extração de dados de imagem"""
        return """
        Analise cuidadosamente a imagem fornecida (dashboard, relatório, planilha, etc).
        Extraia TODAS as métricas de campanha visíveis e retorne um array JSON com objetos contendo:
        - data: data EXACTA mostrada, no formato YYYY-MM-DD. Não invente.
          • Por exemplo, se vir '18 de jun. de 2025', retorne "2025-06-18".
          • Caso não apareça nenhuma data, use a data atual.
        - campaign_name: nome da campanha
        - platform: plataforma (google, facebook, instagram, tiktok, linkedin, other)
        - clicks: número de cliques
        - impressions: número de impressões
        - cost: custo em reais
        - conversions: número de conversões
        
        Retorne apenas o array JSON válido:
        """
    
    def _call_openai_for_extraction(self, prompt: str, image_base64: Optional[str] = None) -> List[Dict[str, Any]]:
        """Chama OpenAI para extração de dados"""
        try:
            messages = [
                {"role": "system", "content": "Você é um assistente especializado em extração de dados de marketing digital. Sempre retorne JSON válido."},
                {"role": "user", "content": prompt}
            ]
            
            # Adiciona imagem se fornecida
            if image_base64:
                messages[1]["content"] = [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            
            content = self._chat_completion(messages, temperature=0.1, max_tokens=2000)
            logger.debug(f"[AI_EXTRACT] Resposta bruta: {content}")

            data = self._safe_json_extract(content)
            if data is None:
                logger.error(f"Erro ao parsear JSON da resposta: {content}")
                return []
            # Garante lista
            if isinstance(data, dict):
                data = [data]
            return data
                
        except Exception as e:
            logger.error(f"Erro na chamada OpenAI: {str(e)}")
            return []
    
    def _validate_and_clean_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Valida, limpa e consolida os dados extraídos."""
        cleaned_data = []
        
        for record in data:
            try:
                cleaned_record = {}
                
                # Data
                def _parse_date_str(date_str: str):
                    """Suporta 'YYYY-MM-DD', 'DD/MM/YYYY', 'DD-MM-YYYY', '15 de junho de 2025',
                    e intervalos '15 de junho de 2025 - 21 de junho de 2025' (usa a 1ª data)."""
                    date_str = date_str.strip().lower()

                    # Se intervalo, pega antes do hífen
                    if ' - ' in date_str:
                        date_str = date_str.split(' - ')[0].strip()
                    if ' até ' in date_str:
                        date_str = date_str.split(' até ')[0].strip()

                    # ISO primeiro
                    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            pass

                    # "DD de mês de YYYY"
                    m = re.match(r'^(\d{1,2}) de ([a-zçãâéêíóõôú]+) de (\d{4})$', date_str)
                    if m:
                        day = int(m.group(1))
                        month_name = m.group(2)
                        year = int(m.group(3))
                        month_map = {
                            'janeiro': 1, 'fevereiro': 2, 'marco': 3, 'março': 3,
                            'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7,
                            'agosto': 8, 'setembro': 9, 'outubro': 10,
                            'novembro': 11, 'dezembro': 12
                        }
                        month = month_map.get(month_name, 1)
                        return datetime(year, month, day)
                    return None

                if 'data' in record and record['data'] not in [None, '', 'null']:
                    if isinstance(record['data'], str):
                        date_obj = _parse_date_str(record['data'])
                        if date_obj:
                            cleaned_record['data'] = date_obj.strftime('%Y-%m-%d')
                        else:
                            cleaned_record['data'] = datetime.now().strftime('%Y-%m-%d')
                    elif isinstance(record['data'], (int, float)):
                        # Suporte a números seriais do Excel (base 1899-12-30)
                        try:
                            excel_base = datetime(1899, 12, 30)
                            date_obj = excel_base + timedelta(days=int(record['data']))
                            cleaned_record['data'] = date_obj.strftime('%Y-%m-%d')
                        except Exception:
                            cleaned_record['data'] = datetime.now().strftime('%Y-%m-%d')
                    elif isinstance(record['data'], datetime):
                        cleaned_record['data'] = record['data'].strftime('%Y-%m-%d')
                    else:
                        # Outros tipos (ex.: pandas.Timestamp)
                        try:
                            cleaned_record['data'] = str(record['data'])[:10]
                        except Exception:
                            cleaned_record['data'] = datetime.now().strftime('%Y-%m-%d')
                else:
                    cleaned_record['data'] = datetime.now().strftime('%Y-%m-%d')
                
                # Campaign name
                campaign_name_val = str(record.get('campaign_name', 'Campanha Sem Nome')).strip()
                if campaign_name_val.lower().startswith(('total', 'conta', 'pesquisa')):
                    continue
                cleaned_record['campaign_name'] = campaign_name_val
                
                # Platform
                platform = str(record.get('platform', 'other')).lower().strip()
                valid_platforms = ['google', 'facebook', 'instagram', 'tiktok', 'linkedin', 'other']
                cleaned_record['platform'] = platform if platform in valid_platforms else 'other'
                
                # Métricas numéricas
                def to_int(value):
                    try:
                        if value in [None, '', 'null']:
                            return 0
                        return int(float(value))
                    except Exception:
                        return 0

                def to_float(value):
                    try:
                        if value in [None, '', 'null']:
                            return 0.0
                        return float(str(value).replace(',', '.'))
                    except Exception:
                        return 0.0

                # -------------------------
                # Mapeia sinônimos se o campo principal não existir
                synonyms_map = {
                    'clicks': ['cliques', 'leads'],
                    'impressions': ['impressoes', 'impr', 'impr.'],
                    'cost': ['custo', 'investimento_realizado', 'investimento', 'invest'],
                    'conversions': ['conversoes', 'conversoes', 'conversoes_', 'conversao', 'conversoes.', 'conversoe_s']
                }

                for primary, synonyms in synonyms_map.items():
                    if primary not in record or record.get(primary) in [None, '', 'null', 0]:
                        for syn in synonyms:
                            if syn in record and record[syn] not in [None, '', 'null']:
                                record[primary] = record[syn]
                                break

                cleaned_record['clicks'] = to_int(record.get('clicks', 0))
                cleaned_record['impressions'] = to_int(record.get('impressions', 0))
                cleaned_record['cost'] = to_float(record.get('cost', 0))
                cleaned_record['conversions'] = to_int(record.get('conversions', 0))
                
                # ------------------------- NOVO: descarta linhas sem métricas -------------------------
                if (
                    cleaned_record['clicks'] == 0 and
                    cleaned_record['impressions'] == 0 and
                    cleaned_record['cost'] == 0 and
                    cleaned_record['conversions'] == 0
                ):
                    # Nenhuma métrica relevante – ignora
                    continue
                
                cleaned_data.append(cleaned_record)
                
            except Exception as e:
                logger.warning(f"Erro ao limpar registro: {record} - {str(e)}")
                continue
        
        # Não consolida duplicados aqui — isso será feito apenas na hora de salvar no banco
        return cleaned_data

    def _safe_json_extract(self, content: str) -> Optional[Any]:
        """Tenta extrair JSON de um texto de maneira robusta."""
        try:
            # Remove blocos markdown ```json ou ```
            if content.startswith('```json'):
                content = content[7:]
            if content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]

            # Tenta parsear diretamente
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Extrai substring entre o primeiro {{ ou [ e o último }} ou ]
                start = None
                end = None
                for i, ch in enumerate(content):
                    if ch == '{' or ch == '[':
                        start = i
                        break
                for j in range(len(content)-1, -1, -1):
                    if content[j] == '}' or content[j] == ']':
                        end = j
                        break
                if start is not None and end is not None and end > start:
                    snippet = content[start:end+1]
                    return json.loads(snippet)
        except Exception as e:
            logger.debug(f"[SAFE_JSON] Falha ao extrair JSON: {str(e)}")
        return None 

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _chat_completion(self, messages, temperature=0.1, max_tokens=500):
        """Abstrai diferença entre openai<1 e >=1"""
        if self._use_new_client:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        else:
            response = self.client.ChatCompletion.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response["choices"][0]["message"]["content"].strip() 
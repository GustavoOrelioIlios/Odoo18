# -*- coding: utf-8 -*-

from pydantic import BaseModel, Field, field_validator, ValidationError, ConfigDict
from typing import List, Optional, Union
from datetime import datetime, date
import re
from decimal import Decimal


class TipoPessoaModel(BaseModel):
    """Modelo para tipo de pessoa do beneficiário"""
    
    codigo_tipo_pessoa: str = Field(
        ...,
        pattern=r'^[FJ]$',
        description="Código do tipo de pessoa (F=Física, J=Jurídica)"
    )
    numero_cadastro_pessoa_fisica: Optional[str] = Field(
        None,
        pattern=r'^\d{11}$',
        description="CPF - 11 dígitos (quando pessoa física)"
    )
    numero_cadastro_nacional_pessoa_juridica: Optional[str] = Field(
        None,
        pattern=r'^\d{14}$',
        description="CNPJ - 14 dígitos (quando pessoa jurídica)"
    )
    
    @field_validator('numero_cadastro_pessoa_fisica', 'numero_cadastro_nacional_pessoa_juridica')
    @classmethod
    def validar_documentos(cls, v, info):
        """Remove formatação dos documentos"""
        if not v:
            return v
        return re.sub(r'[^\d]', '', v)
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class EnderecoModel(BaseModel):
    """Modelo para endereço do beneficiário"""
    
    nome_logradouro: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="Nome do logradouro completo"
    )
    nome_bairro: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Nome do bairro"
    )
    nome_cidade: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Nome da cidade"
    )
    sigla_UF: str = Field(
        ...,
        min_length=2,
        max_length=2,
        pattern=r'^[A-Z]{2}$',
        description="Sigla da UF (2 letras maiúsculas)"
    )
    numero_CEP: str = Field(
        ...,
        pattern=r'^\d{8}$',
        description="CEP - 8 dígitos sem hífen"
    )
    
    @field_validator('numero_CEP')
    @classmethod
    def validar_cep(cls, v):
        """Remove hífen do CEP se presente e valida"""
        if not v:
            return v
        v = v.replace('-', '')
        if not re.match(r'^\d{8}$', v):
            raise ValueError('CEP deve ter exatamente 8 dígitos')
        return v
    
    @field_validator('sigla_UF')
    @classmethod
    def validar_uf(cls, v):
        """Converte UF para maiúsculo"""
        if not v:
            return v
        return v.upper()
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class BeneficiarioItauModel(BaseModel):
    """Modelo para beneficiário conforme API do Itaú - Apenas campos obrigatórios da API"""
    
    id_beneficiario: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="ID único do beneficiário"
    )
    nome_cobranca: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Nome para cobrança"
    )
    tipo_pessoa: TipoPessoaModel = Field(
        ...,
        description="Dados do tipo de pessoa"
    )
    endereco: EnderecoModel = Field(
        ...,
        description="Dados do endereço"
    )
    
    @field_validator('id_beneficiario')
    @classmethod
    def validar_id_beneficiario(cls, v):
        """Valida ID do beneficiário"""
        if not v or not v.strip():
            raise ValueError('ID do beneficiário é obrigatório')
        return v.strip()
    
    @field_validator('nome_cobranca')
    @classmethod
    def validar_nome_cobranca(cls, v):
        """Valida nome para cobrança"""
        if not v or len(v.strip()) < 3:
            raise ValueError('Nome para cobrança deve ter pelo menos 3 caracteres')
        return v.strip()
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class ValidadorBeneficiario:
    """Classe utilitária para validação específica do beneficiário"""
    
    def __init__(self):
        pass
    
    def validar_beneficiario(self, beneficiario_data: dict) -> tuple:
        """
        Valida dados do beneficiário conforme estrutura da API Itaú
        
        Args:
            beneficiario_data: Dict com dados do beneficiário
            
        Returns:
            tuple: (sucesso: bool, dados_validados: dict, erros: list)
        """
        try:
            beneficiario = BeneficiarioItauModel(**beneficiario_data)
            
            erros_adicionais = self._validacoes_adicionais(beneficiario)
            
            if erros_adicionais:
                return False, {}, erros_adicionais
            
            return True, beneficiario.model_dump(), []
            
        except ValidationError as e:
            erros = self._traduzir_erros_beneficiario(e)
            return False, {}, erros
        except Exception as e:
            return False, {}, [{'campo': 'geral', 'mensagem': f'Erro inesperado: {str(e)}'}]
    
    def _validacoes_adicionais(self, beneficiario: BeneficiarioItauModel) -> list:
        """Validações de negócio específicas"""
        erros = []
        
        tipo_pessoa = beneficiario.tipo_pessoa.codigo_tipo_pessoa
        cpf = beneficiario.tipo_pessoa.numero_cadastro_pessoa_fisica
        cnpj = beneficiario.tipo_pessoa.numero_cadastro_nacional_pessoa_juridica
        
        if tipo_pessoa == 'F':
            if not cpf:
                erros.append({
                    'campo': 'tipo_pessoa.numero_cadastro_pessoa_fisica',
                    'mensagem': 'CPF é obrigatório para pessoa física'
                })
            if cnpj:
                erros.append({
                    'campo': 'tipo_pessoa.numero_cadastro_nacional_pessoa_juridica',
                    'mensagem': 'CNPJ não deve ser preenchido para pessoa física'
                })
        
        elif tipo_pessoa == 'J':
            if not cnpj:
                erros.append({
                    'campo': 'tipo_pessoa.numero_cadastro_nacional_pessoa_juridica',
                    'mensagem': 'CNPJ é obrigatório para pessoa jurídica'
                })
            if cpf:
                erros.append({
                    'campo': 'tipo_pessoa.numero_cadastro_pessoa_fisica',
                    'mensagem': 'CPF não deve ser preenchido para pessoa jurídica'
                })
        
        return erros
    
    def _traduzir_erros_beneficiario(self, validation_error: ValidationError) -> list:
        """Traduz erros de validação para português com foco no beneficiário"""
        erros_traduzidos = []
        
        for erro in validation_error.errors():
            campo = '.'.join(str(loc) for loc in erro['loc'])
            tipo_erro = erro['type']
            mensagem = erro['msg']
            
            if tipo_erro == 'missing':
                mensagem_pt = f"Campo '{campo}' é obrigatório"
            elif tipo_erro == 'string_pattern_mismatch':
                if 'codigo_tipo_pessoa' in campo:
                    mensagem_pt = f"Campo '{campo}' deve ser 'F' (Física) ou 'J' (Jurídica)"
                elif 'numero_cadastro_pessoa_fisica' in campo:
                    mensagem_pt = f"Campo '{campo}' deve ter exatamente 11 dígitos (CPF)"
                elif 'numero_cadastro_nacional_pessoa_juridica' in campo:
                    mensagem_pt = f"Campo '{campo}' deve ter exatamente 14 dígitos (CNPJ)"
                elif 'sigla_UF' in campo:
                    mensagem_pt = f"Campo '{campo}' deve ter 2 letras maiúsculas (ex: SP, RJ)"
                elif 'numero_CEP' in campo:
                    mensagem_pt = f"Campo '{campo}' deve ter exatamente 8 dígitos"
                else:
                    mensagem_pt = f"Campo '{campo}' tem formato inválido"
            elif 'string_too_short' in tipo_erro:
                min_length = erro.get('ctx', {}).get('min_length', 'X')
                mensagem_pt = f"Campo '{campo}' deve ter pelo menos {min_length} caracteres"
            elif 'string_too_long' in tipo_erro:
                max_length = erro.get('ctx', {}).get('max_length', 'X')
                mensagem_pt = f"Campo '{campo}' deve ter no máximo {max_length} caracteres"
            else:
                mensagem_pt = f"Campo '{campo}': {mensagem}"
            
            erros_traduzidos.append({
                'campo': campo,
                'tipo': tipo_erro,
                'mensagem': mensagem_pt,
                'valor_informado': erro.get('input', 'N/A')
            })
        
        return erros_traduzidos
    
    def formatar_erros_para_exibicao(self, erros: list) -> str:
        """Formata lista de erros para exibição ao usuário"""
        if not erros:
            return ""
        
        linhas = ["⚠️ Erros de validação do beneficiário encontrados:"]
        for i, erro in enumerate(erros, 1):
            linhas.append(f"{i}. {erro['mensagem']}")
            if erro.get('valor_informado') and erro['valor_informado'] != 'N/A':
                linhas.append(f"   Valor informado: {erro['valor_informado']}")
        
        return "\n".join(linhas)
    
    def exemplo_beneficiario_valido(self) -> dict:
        """Retorna exemplo de beneficiário válido para testes"""
        return {
            "id_beneficiario": "150000052061",
            "nome_cobranca": "Antonio Coutinho SA",
            "tipo_pessoa": {
                "codigo_tipo_pessoa": "J",
                "numero_cadastro_nacional_pessoa_juridica": "12345678901234"
            },
            "endereco": {
                "nome_logradouro": "rua dona ana neri, 368",
                "nome_bairro": "Mooca",
                "nome_cidade": "Sao Paulo",
                "sigla_UF": "SP",
                "numero_CEP": "12345678"
            }
        }

class PydanticI18nPtBr:
    """Configuração de tradução para português brasileiro"""
    
    @staticmethod
    def setup_translations():
        """Configura traduções personalizadas para português"""
        translations = {
            'en': {
                'Field required': 'Campo obrigatório',
                'ensure this value is greater than 0': 'valor deve ser maior que 0',
                'ensure this value has at most {limit_value} characters': 'máximo de {limit_value} caracteres',
                'ensure this value has at least {limit_value} characters': 'mínimo de {limit_value} caracteres',
                'string does not match regex': 'formato inválido',
                'invalid datetime format': 'formato de data inválido',
                'value is not a valid email address': 'email inválido',
                'value is not a valid decimal': 'valor decimal inválido',
            }
        }
        return translations


class PagadorPessoaModel(BaseModel):
    """Modelo para dados da pessoa do pagador (estrutura aninhada)"""
    
    nome_pessoa: str = Field(
        ..., 
        min_length=3,
        max_length=100,
        description="Nome completo da pessoa"
    )
    nome_fantasia: Optional[str] = Field(
        None,
        max_length=100,
        description="Nome fantasia (pode ser igual ao nome_pessoa)"
    )
    tipo_pessoa: TipoPessoaModel = Field(
        ...,
        description="Dados do tipo de pessoa e documentos"
    )
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class PagadorModel(BaseModel):
    """Modelo para validação de dados do pagador (estrutura aninhada conforme API Itaú)"""
    
    pessoa: PagadorPessoaModel = Field(
        ...,
        description="Dados da pessoa do pagador"
    )
    endereco: EnderecoModel = Field(
        ...,
        description="Dados do endereço do pagador"
    )
    texto_endereco_email: Optional[str] = Field(
        None,
        max_length=100,
        pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        description="Email válido"
    )
    
    @field_validator('texto_endereco_email')
    @classmethod
    def validar_email(cls, v):
        """Validação adicional de email"""
        if v and len(v) > 100:
            raise ValueError('Email muito longo (máximo 100 caracteres)')
        return v
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class BeneficiarioModel(BaseModel):
    """Modelo para validação de dados do beneficiário (versão antiga)"""
    
    nome_cobranca: str = Field(
        ..., 
        min_length=3,
        max_length=100,
        description="Nome para cobrança"
    )
    nome_fantasia: Optional[str] = Field(
        None,
        max_length=100,
        description="Nome fantasia"
    )
    cnpj: str = Field(
        ...,
        pattern=r'^\d{14}$',
        description="CNPJ apenas números (14 dígitos)"
    )
    codigo_banco: str = Field(
        ...,
        pattern=r'^\d{3}$',
        description="Código do banco (3 dígitos)"
    )
    agencia: str = Field(
        ...,
        pattern=r'^\d{4}$',
        description="Agência (4 dígitos)"
    )
    conta: str = Field(
        ...,
        min_length=4,
        max_length=10,
        pattern=r'^\d+$',
        description="Conta corrente apenas números"
    )
    digito_conta: str = Field(
        ...,
        pattern=r'^\d{1}$',
        description="Dígito da conta (1 dígito)"
    )
    
    logradouro: str = Field(..., min_length=5, max_length=200)
    bairro: str = Field(..., min_length=2, max_length=100)
    cidade: str = Field(..., min_length=2, max_length=100)
    uf: str = Field(..., min_length=2, max_length=2, pattern=r'^[A-Z]{2}$')
    cep: str = Field(..., pattern=r'^\d{5}-?\d{3}$')
    
    @field_validator('cnpj')
    @classmethod
    def validar_cnpj_beneficiario(cls, v):
        """Remove formatação do CNPJ"""
        return re.sub(r'[^\d]', '', v) if v else v
    
    @field_validator('cep')
    @classmethod
    def validar_cep_beneficiario(cls, v):
        """Remove hífen do CEP se presente"""
        return v.replace('-', '') if v else v
    
    @field_validator('uf')
    @classmethod
    def validar_uf_beneficiario(cls, v):
        """Converte UF para maiúsculo"""
        return v.upper() if v else v
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class BoletoIndividualModel(BaseModel):
    """Modelo para validação de dados individuais do boleto"""
    
    valor_titulo: Union[str, float, Decimal] = Field(
        ...,
        description="Valor do título"
    )
    id_boleto_individual: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="ID único do boleto"
    )
    situacao_geral_boleto: str = Field(
        default="Em Aberto",
        description="Situação geral do boleto"
    )
    status_vencimento: str = Field(
        default="a vencer",
        description="Status do vencimento"
    )
    numero_nosso_numero: str = Field(
        ...,
        min_length=1,
        max_length=11,
        pattern=r'^\d+$',
        description="Nosso número (apenas dígitos)"
    )
    data_vencimento: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Data de vencimento no formato YYYY-MM-DD"
    )
    texto_seu_numero: Optional[str] = Field(
        None,
        max_length=20,
        description="Seu número (referência do cliente)"
    )
    data_limite_pagamento: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Data limite para pagamento no formato YYYY-MM-DD"
    )
    texto_uso_beneficiario: Optional[str] = Field(
        None,
        max_length=200,
        description="Texto de uso do beneficiário"
    )
    
    @field_validator('valor_titulo')
    @classmethod
    def validar_valor(cls, v):
        """Valida e converte valor para string"""
        if isinstance(v, (int, float, Decimal)):
            v = str(v)
        
        try:
            valor_float = float(v)
            if valor_float <= 0:
                raise ValueError('Valor deve ser maior que zero')
            return f"{valor_float:.2f}"
        except ValueError:
            raise ValueError('Valor inválido')
    
    @field_validator('data_vencimento', 'data_limite_pagamento')
    @classmethod
    def validar_data(cls, v):
        """Valida formato da data"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Data deve estar no formato YYYY-MM-DD')
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class JurosModel(BaseModel):
    """Modelo para configurações de juros"""
    
    codigo_tipo_juros: str = Field(
        ...,
        pattern=r'^(90|91|92|93|05)$',
        description="Código do tipo de juros (90=% Mensal, 91=% Diário, 92=% Anual, 93=Valor Diário, 05=Isento)"
    )
    data_juros: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Data de início dos juros no formato YYYY-MM-DD"
    )
    percentual_juros: Optional[str] = Field(
        None,
        pattern=r'^\d{12}$',
        description="Percentual de juros formatado como string de 12 dígitos (usado para códigos 90, 91, 92)"
    )
    valor_juros: Optional[str] = Field(
        None,
        description="Valor fixo de juros (usado para código 93)"
    )
    
    @field_validator('data_juros')
    @classmethod
    def validar_data_juros(cls, v):
        """Valida formato da data de juros"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Data de juros deve estar no formato YYYY-MM-DD')
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class MultaModel(BaseModel):
    """Modelo para configurações de multa"""
    
    codigo_tipo_multa: str = Field(
        ...,
        pattern=r'^(01|02|03)$',
        description="Código do tipo de multa (01=Valor Fixo, 02=Percentual, 03=Isento)"
    )
    data_multa: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Data de início da multa no formato YYYY-MM-DD"
    )
    valor_multa: Optional[str] = Field(
        None,
        description="Valor fixo da multa (usado para código 01)"
    )
    percentual_multa: Optional[str] = Field(
        None,
        pattern=r'^\d{12}$',
        description="Percentual de multa formatado como string de 12 dígitos (usado para código 02)"
    )
    
    @field_validator('data_multa')
    @classmethod
    def validar_data_multa(cls, v):
        """Valida formato da data de multa"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Data de multa deve estar no formato YYYY-MM-DD')
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class DescontoIndividualModel(BaseModel):
    """Modelo para desconto individual - suporta tanto percentual quanto valor fixo"""
    
    data_desconto: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Data do desconto no formato YYYY-MM-DD"
    )
    percentual_desconto: Optional[str] = Field(
        None,
        pattern=r'^\d{12}$',
        description="Percentual de desconto formatado como string de 12 dígitos (para códigos 02, 90)"
    )
    valor_desconto: Optional[str] = Field(
        None,
        pattern=r'^\d{17}$',
        description="Valor fixo de desconto formatado como string de 17 dígitos (para códigos 01, 91)"
    )
    
    @field_validator('data_desconto')
    @classmethod
    def validar_data_desconto(cls, v):
        """Valida formato da data de desconto"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Data de desconto deve estar no formato YYYY-MM-DD')
    
    @field_validator('percentual_desconto', 'valor_desconto')
    @classmethod
    def validar_desconto_exclusivo(cls, v, info):
        """Valida que apenas um tipo de desconto seja informado por vez"""
        if info.data.get('percentual_desconto') and info.data.get('valor_desconto'):
            raise ValueError('Apenas um tipo de desconto pode ser informado (percentual OU valor)')
        return v
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class DescontoModel(BaseModel):
    """Modelo para configurações de desconto conforme API Itaú"""
    
    codigo_tipo_desconto: str = Field(
        ...,
        pattern=r'^(00|01|02|90|91)$',
        description="Código do tipo de desconto conforme API Itaú: "
                   "00=Sem Desconto, 01=Valor Fixo, 02=Percentual, "
                   "90=Percentual por Antecipação, 91=Valor por Antecipação"
    )
    descontos: List[DescontoIndividualModel] = Field(
        ...,
        min_length=1,
        description="Lista de descontos individuais (obrigatório quando código != 00)"
    )
    
    @field_validator('descontos')
    @classmethod
    def validar_descontos_consistencia(cls, v, info):
        """Valida consistência entre código de desconto e linhas de desconto"""
        codigo = info.data.get('codigo_tipo_desconto')
        
        if codigo == '00' and v:
            raise ValueError('Quando código é 00 (Sem Desconto), não deve haver linhas de desconto')
        
        if codigo != '00' and not v:
            raise ValueError('Quando código != 00, deve haver pelo menos uma linha de desconto')
        
        for desconto in v:
            if codigo in ['02', '90']:
                if desconto.valor_desconto:
                    raise ValueError(f'Para código {codigo} (percentual), use apenas percentual_desconto')
                if not desconto.percentual_desconto:
                    raise ValueError(f'Para código {codigo} (percentual), percentual_desconto é obrigatório')
            
            elif codigo in ['01', '91']:
                if desconto.percentual_desconto:
                    raise ValueError(f'Para código {codigo} (valor fixo), use apenas valor_desconto')
                if not desconto.valor_desconto:
                    raise ValueError(f'Para código {codigo} (valor fixo), valor_desconto é obrigatório')
        
        return v
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class ProtestoModel(BaseModel):
    """Modelo para configurações de protesto"""
    
    codigo_tipo_protesto: int = Field(
        ...,
        ge=1,
        le=9,
        description="Código de protesto (1=Protestar, 4=Não Protestar, 9=Cancelar Protesto)"
    )
    quantidade_dias_protesto: Optional[int] = Field(
        None,
        ge=1,
        le=99,
        description="Dias para protesto (entre 1 e 99)"
    )
    protesto_falimentar: bool = Field(
        default=True,
        description="Indica se é protesto falimentar"
    )


class NegativacaoModel(BaseModel):
    """Modelo para configurações de negativação"""
    
    codigo_tipo_negativacao: int = Field(
        ...,
        ge=2,
        le=10,
        description="Código de negativação (2=Negativar, 5=Não Negativar, 10=Cancelar Negativação)"
    )
    quantidade_dias_negativacao: Optional[int] = Field(
        None,
        ge=2,
        le=99,
        description="Dias para negativação (entre 2 e 99)"
    )
    
    @field_validator('quantidade_dias_negativacao')
    @classmethod
    def validar_dias_negativacao(cls, v, info):
        """Valida que quantidade_dias_negativacao é obrigatório quando codigo_tipo_negativacao é 2"""
        codigo_negativacao = info.data.get('codigo_tipo_negativacao')
        if codigo_negativacao == 2 and not v:
            raise ValueError('Dias para negativação é obrigatório quando código é 2 (Negativar)')
        return v
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class BoletoModel(BaseModel):
    """Modelo principal para validação completa do boleto com campos adicionais"""
    
    codigo_carteira: str = Field(
        ...,
        pattern=r'^\d{3}$',
        description="Código da carteira (3 dígitos) - OBRIGATÓRIO"
    )
    codigo_especie: str = Field(
        ...,
        pattern=r'^\d{2}$',
        description="Código da espécie (2 dígitos) - OBRIGATÓRIO"
    )
    descricao_especie: Optional[str] = Field(
        None,
        max_length=100,
        description="Descrição da espécie do título"
    )
    descricao_instrumento_cobranca: Optional[str] = Field(
        default="boleto",
        max_length=50,
        description="Descrição do instrumento de cobrança (fixo como 'boleto')"
    )
    codigo_aceite: str = Field(
        default="S",
        pattern=r'^[SN]$',
        description="Código de aceite (S ou N)"
    )
    tipo_boleto: str = Field(
        default="proposta",
        description="Tipo do boleto"
    )
    data_emissao: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Data de emissão no formato YYYY-MM-DD"
    )
    
    juros: Optional[JurosModel] = Field(
        None,
        description="Configurações de juros (opcional)"
    )
    multa: Optional[MultaModel] = Field(
        None,
        description="Configurações de multa (opcional)"
    )
    desconto: Optional[DescontoModel] = Field(
        None,
        description="Configurações de desconto (opcional)"
    )
    
    protesto: Optional[ProtestoModel] = Field(
        None,
        description="Configurações de protesto (opcional)"
    )
    negativacao: Optional[NegativacaoModel] = Field(
        None,
        description="Configurações de negativação (opcional)"
    )
    
    dados_individuais_boleto: List[BoletoIndividualModel] = Field(
        ...,
        min_length=1,
        description="Lista de boletos individuais"
    )
    
    @field_validator('data_emissao')
    @classmethod
    def validar_data_emissao(cls, v):
        """Valida formato da data de emissão"""
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Data de emissão deve estar no formato YYYY-MM-DD')
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True
    )


class BoletoCompletoModel(BaseModel):
    """Modelo completo para validação de todos os dados do boleto"""
    
    beneficiario: BeneficiarioItauModel
    pagador: PagadorModel
    boleto: BoletoModel
    
    model_config = ConfigDict(
        validate_assignment=True
    )


class ValidadorBoleto:
    """Classe utilitária para validação de boletos com mensagens em português"""
    
    def __init__(self):
        self.translations = PydanticI18nPtBr.setup_translations()
    
    def validar_dados_completos(self, beneficiario_data: dict, pagador_data: dict, boleto_data: dict) -> tuple:
        """
        Valida todos os dados do boleto
        
        Returns:
            tuple: (sucesso: bool, dados_validados: dict, erros: list)
        """
        try:
            beneficiario = BeneficiarioItauModel(**beneficiario_data)
            pagador = PagadorModel(**pagador_data)
            boleto = BoletoModel(**boleto_data)
            
            boleto_completo = BoletoCompletoModel(
                beneficiario=beneficiario,
                pagador=pagador,
                boleto=boleto
            )
            
            return True, boleto_completo.model_dump(), []
            
        except ValidationError as e:
            erros = self._traduzir_erros(e)
            return False, {}, erros
    
    def _traduzir_erros(self, validation_error: ValidationError) -> list:
        """Traduz erros de validação para português"""
        erros_traduzidos = []
        
        for erro in validation_error.errors():
            campo = '.'.join(str(loc) for loc in erro['loc'])
            tipo_erro = erro['type']
            mensagem = erro['msg']
            
            if tipo_erro == 'missing':
                mensagem_pt = f"Campo '{campo}' é obrigatório"
            elif tipo_erro == 'string_pattern_mismatch':
                mensagem_pt = f"Campo '{campo}' tem formato inválido"
            elif 'string_too_short' in tipo_erro:
                mensagem_pt = f"Campo '{campo}' deve ter pelo menos {erro.get('ctx', {}).get('min_length', 'X')} caracteres"
            elif 'string_too_long' in tipo_erro:
                mensagem_pt = f"Campo '{campo}' deve ter no máximo {erro.get('ctx', {}).get('max_length', 'X')} caracteres"
            elif 'greater_than' in tipo_erro:
                mensagem_pt = f"Campo '{campo}' deve ser maior que {erro.get('ctx', {}).get('gt', '0')}"
            elif 'value_error' in tipo_erro:
                mensagem_pt = f"Campo '{campo}': {mensagem}"
            else:
                mensagem_pt = f"Campo '{campo}': {mensagem}"
            
            erros_traduzidos.append({
                'campo': campo,
                'tipo': tipo_erro,
                'mensagem': mensagem_pt,
                'valor_informado': erro.get('input', 'N/A')
            })
        
        return erros_traduzidos
    
    def formatar_erros_para_exibicao(self, erros: list) -> str:
        """Formata lista de erros para exibição ao usuário"""
        if not erros:
            return ""
        
        linhas = ["⚠️ Erros de validação encontrados:"]
        for i, erro in enumerate(erros, 1):
            linhas.append(f"{i}. {erro['mensagem']}")
            if erro['valor_informado'] != 'N/A':
                linhas.append(f"   Valor informado: {erro['valor_informado']}")
        
        return "\n".join(linhas) 
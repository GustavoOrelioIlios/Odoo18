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
        # Remove hífen se presente
        v = v.replace('-', '')
        # Valida se tem exatamente 8 dígitos
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
            # Valida usando o modelo Pydantic
            beneficiario = BeneficiarioItauModel(**beneficiario_data)
            
            # Validações adicionais específicas
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
        
        # Valida consistência entre tipo de pessoa e documentos
        tipo_pessoa = beneficiario.tipo_pessoa.codigo_tipo_pessoa
        cpf = beneficiario.tipo_pessoa.numero_cadastro_pessoa_fisica
        cnpj = beneficiario.tipo_pessoa.numero_cadastro_nacional_pessoa_juridica
        
        if tipo_pessoa == 'F':  # Pessoa Física
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
        
        elif tipo_pessoa == 'J':  # Pessoa Jurídica
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
            
            # Tradução personalizada baseada no tipo de erro
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


# ===== MODELOS ANTIGOS (MANTIDOS PARA COMPATIBILIDADE) =====
# Estes modelos serão usados quando migrarmos outras partes da validação

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


# Mantendo modelos antigos para compatibilidade temporária
class PagadorModel(BaseModel):
    """Modelo para validação de dados do pagador"""
    
    nome_pagador: str = Field(
        ..., 
        min_length=3,
        max_length=100,
        description="Nome completo do pagador"
    )
    cpf: Optional[str] = Field(
        None,
        pattern=r'^\d{11}$',
        description="CPF apenas números (11 dígitos)"
    )
    cnpj: Optional[str] = Field(
        None,
        pattern=r'^\d{14}$',
        description="CNPJ apenas números (14 dígitos)"
    )
    telefone: Optional[str] = Field(
        None,
        min_length=10,
        max_length=15,
        pattern=r'^\d{10,15}$',
        description="Telefone apenas números (10 a 15 dígitos)"
    )
    email: Optional[str] = Field(
        None,
        max_length=100,
        pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        description="Email válido"
    )
    
    # Campos de endereço usando modelo separado
    logradouro: str = Field(..., min_length=5, max_length=200)
    bairro: str = Field(..., min_length=2, max_length=100)
    cidade: str = Field(..., min_length=2, max_length=100)
    uf: str = Field(..., min_length=2, max_length=2, pattern=r'^[A-Z]{2}$')
    cep: str = Field(..., pattern=r'^\d{5}-?\d{3}$')
    
    @field_validator('cpf', 'cnpj')
    @classmethod
    def validar_documento(cls, v, info):
        """Valida CPF ou CNPJ"""
        if not v:
            return v
            
        # Remove formatação
        v = re.sub(r'[^\d]', '', v)
        
        if info.field_name == 'cpf' and len(v) != 11:
            raise ValueError('CPF deve ter 11 dígitos')
        elif info.field_name == 'cnpj' and len(v) != 14:
            raise ValueError('CNPJ deve ter 14 dígitos')
            
        return v
    
    @field_validator('email')
    @classmethod
    def validar_email(cls, v):
        """Validação adicional de email"""
        if v and len(v) > 100:
            raise ValueError('Email muito longo (máximo 100 caracteres)')
        return v
    
    @field_validator('cep')
    @classmethod
    def validar_cep_pagador(cls, v):
        """Remove hífen do CEP se presente"""
        return v.replace('-', '') if v else v
    
    @field_validator('uf')
    @classmethod
    def validar_uf_pagador(cls, v):
        """Converte UF para maiúsculo"""
        return v.upper() if v else v
    
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
    
    # Campos de endereço
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
        
        # Verifica se é um número válido
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


class BoletoModel(BaseModel):
    """Modelo principal para validação completa do boleto"""
    
    dados_individuais_boleto: List[BoletoIndividualModel] = Field(
        ...,
        min_length=1,
        description="Lista de boletos individuais"
    )
    codigo_especie: str = Field(
        default="01",
        pattern=r'^\d{2}$',
        description="Código da espécie (2 dígitos)"
    )
    tipo_boleto: str = Field(
        default="proposta",
        description="Tipo do boleto"
    )
    codigo_carteira: str = Field(
        default="112",
        pattern=r'^\d{3}$',
        description="Código da carteira (3 dígitos)"
    )
    codigo_aceite: str = Field(
        default="S",
        pattern=r'^[SN]$',
        description="Código de aceite (S ou N)"
    )
    data_emissao: str = Field(
        ...,
        pattern=r'^\d{4}-\d{2}-\d{2}$',
        description="Data de emissão no formato YYYY-MM-DD"
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
            # Valida dados individuais
            beneficiario = BeneficiarioItauModel(**beneficiario_data)
            pagador = PagadorModel(**pagador_data)
            boleto = BoletoModel(**boleto_data)
            
            # Valida dados completos
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
            
            # Tradução personalizada baseada no tipo de erro
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
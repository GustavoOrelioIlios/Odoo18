# -*- coding: utf-8 -*-

from typing import Optional, List, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict, ValidationError
from datetime import date, datetime
from decimal import Decimal
import re

def format_decimal_to_str(value: Union[float, Decimal], total_digits: int, decimal_places: int) -> str:
    if value is None:
        return ""
    d_value = Decimal(str(value))
    scaled_value = int(d_value * (10 ** decimal_places))
    return f"{scaled_value:0{total_digits}d}"

class PagadorModel(BaseModel):
    """Modelo Pydantic para dados do pagador"""
    numeroCpfCnpj: str = Field(..., description="CPF/CNPJ do pagador")
    nome: str = Field(..., description="Nome do pagador")
    endereco: str = Field(..., description="Endereço do pagador")
    bairro: str = Field(..., description="Bairro do pagador")
    cidade: str = Field(..., description="Cidade do pagador")
    cep: str = Field(..., description="CEP do pagador")
    uf: str = Field(..., description="UF do pagador")
    email: Optional[str] = Field(None, description="E-mail do pagador")

    model_config = ConfigDict(populate_by_name=True, extra='ignore', str_strip_whitespace=True)

    @field_validator('numeroCpfCnpj')
    def validate_cpf_cnpj(cls, v):
        cleaned_v = re.sub(r'[^0-9]', '', v)
        if len(cleaned_v) == 11:
            if not re.fullmatch(r'\d{11}', cleaned_v):
                raise ValueError("CPF inválido. Deve conter 11 dígitos numéricos.")
        elif len(cleaned_v) == 14:
            if not re.fullmatch(r'\d{14}', cleaned_v):
                raise ValueError("CNPJ inválido. Deve conter 14 dígitos numéricos.")
        else:
            raise ValueError("CPF/CNPJ deve conter 11 (CPF) ou 14 (CNPJ) dígitos numéricos.")
        return cleaned_v

    @field_validator('cep')
    def validate_cep(cls, v):
        cleaned_v = re.sub(r'[^0-9]', '', v)
        if not re.fullmatch(r'\d{8}', cleaned_v):
            raise ValueError("CEP inválido. Deve conter 8 dígitos numéricos.")
        return cleaned_v

    @field_validator('uf')
    def validate_uf(cls, v):
        if not re.fullmatch(r'[A-Z]{2}', v):
            raise ValueError("UF inválida. Deve conter 2 letras maiúsculas.")
        return v
    
    @field_validator('email')
    def validate_email(cls, v):
        if v is not None and not re.fullmatch(r'[^@]+@[^@]+\.[^@]+', v):
            raise ValueError("Formato de e-mail inválido.")
        return v

class BeneficiarioFinalModel(BaseModel):
    """Modelo Pydantic para dados do beneficiário final"""
    numeroCpfCnpj: str = Field(..., description="CPF/CNPJ do beneficiário final")
    nome: str = Field(..., description="Nome do beneficiário final")

    model_config = ConfigDict(populate_by_name=True, extra='ignore', str_strip_whitespace=True)

    @field_validator('numeroCpfCnpj')
    def validate_cpf_cnpj(cls, v):
        cleaned_v = re.sub(r'[^0-9]', '', v)
        if len(cleaned_v) == 11:
            if not re.fullmatch(r'\d{11}', cleaned_v):
                raise ValueError("CPF inválido. Deve conter 11 dígitos numéricos.")
        elif len(cleaned_v) == 14:
            if not re.fullmatch(r'\d{14}', cleaned_v):
                raise ValueError("CNPJ inválido. Deve conter 14 dígitos numéricos.")
        else:
            raise ValueError("CPF/CNPJ deve conter 11 (CPF) ou 14 (CNPJ) dígitos numéricos.")
        return cleaned_v


class RateioCreditosItemModel(BaseModel):
    """Modelo Pydantic para item de rateio de créditos"""
    numeroBanco: int = Field(..., description="Número do banco")
    numeroAgencia: int = Field(..., description="Número da agência")
    numeroContaCorrente: int = Field(..., description="Número da conta corrente")
    valor: float = Field(..., description="Valor do rateio")

    model_config = ConfigDict(populate_by_name=True, extra='ignore', str_strip_whitespace=True)

class SicoobBoletoRequestPayload(BaseModel):
    """Modelo Pydantic principal para requisição de boleto Sicoob"""
    dataEmissao: str = Field(
        ..., 
        description="Data de emissão do boleto. Caso não seja informado, o sistema atribui a data de registro do boleto no Sisbr. Formato: YYYY-MM-dd"
    )
    nossoNumero: int = Field(
        ..., 
        description="Número que identifica o boleto de cobrança no Sisbr. Gerado pela sequência do Odoo."
    )
    seuNumero: str = Field(
        ..., 
        description="Número identificador do boleto no sistema do beneficiário (número da fatura). Tamanho máximo 18"
    )
    valor: float = Field(
        ..., 
        gt=0, 
        description="Valor nominal do boleto"
    )
    dataVencimento: str = Field(
        ..., 
        description="Data de vencimento do boleto. Formato: YYYY-MM-dd"
    )
    dataLimitePagamento: str = Field(
        ..., 
        description="Data limite para pagamento do boleto. Formato: YYYY-MM-dd"
    )
    aceite: bool = Field(
        True, 
        description="Identificador do aceite do boleto"
    )
    codigoEspecieDocumento: str = Field(
        ..., 
        description="Espécie do Documento. Ex: DM (Duplicata Mercantil), DS (Duplicata de Serviço), etc."
    )
    
    numeroCliente: int = Field(..., description="Número do cliente no Sicoob")
    codigoModalidade: int = Field(..., description="Código da modalidade de cobrança")
    numeroContaCorrente: int = Field(..., description="Número da conta corrente")
    pagador: PagadorModel = Field(..., description="Dados do pagador")
    beneficiarioFinal: Optional[BeneficiarioFinalModel] = Field(None, description="Dados do beneficiário final")
    
    mensagensInstrucao: Optional[List[str]] = Field(None, description="Mensagens de instrução")
    numeroContratoCobranca: Optional[int] = Field(None, description="Número do contrato de cobrança")
    
    identificacaoBoletoEmpresa: Optional[str] = Field(None, description="Campo para uso da empresa do beneficiário para identificação do boleto")
    identificacaoEmissaoBoleto: Optional[int] = Field(None, description="1 – Banco Emite, 2 – Cliente Emite")
    identificacaoDistribuicaoBoleto: Optional[int] = Field(None, description="1 – Banco Distribui, 2 – Cliente Distribui")
    gerarPdf: Optional[bool] = Field(None, description="Define se o PDF do boleto deve ser gerado")

    tipoJurosMora: Optional[int] = Field(None, description="Tipo de juros de mora")
    valorJurosMora: Optional[float] = Field(None, description="Valor ou percentual dos juros de mora")
    dataJurosMora: Optional[str] = Field(None, description="Data de início dos juros de mora")

    tipoMulta: Optional[int] = Field(None, description="Tipo de multa")
    valorMulta: Optional[float] = Field(None, description="Valor da multa quando tipo for valor fixo")
    percentualMulta: Optional[float] = Field(None, description="Percentual da multa quando tipo for percentual")
    dataMulta: Optional[str] = Field(None, description="Data de início da multa")

    tipoDesconto: int = Field(..., description="Tipo de desconto (0=Sem desconto, 1=Valor fixo, 2=Percentual)")
    dataPrimeiroDesconto: Optional[str] = Field(None, description="Data do primeiro desconto")
    valorPrimeiroDesconto: Optional[float] = Field(None, description="Valor ou percentual do primeiro desconto")

    numeroParcela: int = Field(..., description="Número da parcela do boleto")

    codigoCadastrarPIX: Optional[int] = Field(None, description="Código para cadastrar PIX (0=Não gerar, 1=Gerar)")

    model_config = ConfigDict(populate_by_name=True, extra='ignore', str_strip_whitespace=True)

    @field_validator('dataEmissao', 'dataVencimento', 'dataLimitePagamento', 'dataJurosMora', 'dataMulta', 'dataPrimeiroDesconto')
    def validate_date_format(cls, v):
        """Valida e formata as datas no formato YYYY-MM-dd"""
        if v is None:
            return v
        if isinstance(v, date):
            return v.isoformat()
        
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError("Formato de data inválido. Use YYYY-MM-dd.")

    @field_validator('seuNumero')
    def validate_seu_numero(cls, v):
        """Valida o tamanho do seu número"""
        if len(v) > 18:
            raise ValueError("seuNumero não pode ter mais de 18 caracteres")
        return v

    @field_validator('codigoEspecieDocumento')
    def validate_especie_documento(cls, v):
        """Valida o código da espécie do documento"""
        especies_validas = {
            'CH', 'DM', 'DMI', 'DS', 'DSI', 'DR', 'LC', 'NCC', 'NCE', 'NCI', 'NCR', 'NP', 'NPR', 
            'TM', 'TS', 'NS', 'RC', 'FAT', 'ND', 'AP', 'ME', 'PC', 'NF', 'DD', 'CPR', 'WR', 
            'DAE', 'DAM', 'DAU', 'EC', 'CPS', 'OUT'
        }
        if v not in especies_validas:
            raise ValueError(f"Espécie de documento inválida. Valores válidos: {', '.join(sorted(especies_validas))}")
        return v

class SicoobBoletoValidator:
    """Classe utilitária para validação de dados do boleto Sicoob"""
    
    @staticmethod
    def validar_payload(dados: dict) -> tuple[bool, dict, str]:
        """
        Valida os dados do boleto usando os modelos Pydantic
        
        Args:
            dados (dict): Dicionário com os dados do boleto
            
        Returns:
            tuple: (sucesso, dados_validados, mensagem)
                - sucesso (bool): True se a validação foi bem sucedida
                - dados_validados (dict): Dados validados e formatados pelo Pydantic
                - mensagem (str): Mensagem de erro em caso de falha
        """
        try:
            modelo = SicoobBoletoRequestPayload(**dados)
            return True, modelo.model_dump(exclude_none=True), ""
        except ValidationError as e:
            erros = []
            for error in e.errors():
                loc_path = " -> ".join(str(loc) for loc in error['loc'])
                msg = error['msg']
                
                if "field required" in msg:
                    msg = "Campo obrigatório."
                elif "Value must be greater than 0" in msg:
                    msg = "Deve ser maior que zero."
                elif "Formato de data inválido" in msg:
                    msg = "Formato de data inválido. Use YYYY-MM-dd."
                elif "Value error, " in msg:
                    msg = msg.replace("Value error, ", "")
                
                erros.append(f"Campo '{loc_path}': {msg}")
            
            return False, {}, "\n".join(erros)
        except Exception as e:
            return False, {}, f"Erro inesperado durante a validação: {str(e)}"

    @staticmethod
    def formatar_erros_para_exibicao(erros: str) -> str:
        """
        Formata os erros de validação para exibição ao usuário
        
        Args:
            erros (str): String com os erros de validação
            
        Returns:
            str: Erros formatados para exibição
        """
        if not erros:
            return ""
        
        return "Erros de validação encontrados:\n" + erros
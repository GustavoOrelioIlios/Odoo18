# -*- coding: utf-8 -*-

from typing import Optional, List, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict
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

    model_config = ConfigDict(populate_by_name=True, extra='forbid', str_strip_whitespace=True)

class BeneficiarioFinalModel(BaseModel):
    """Modelo Pydantic para dados do beneficiário final"""
    numeroCpfCnpj: str = Field(..., description="CPF/CNPJ do beneficiário final")
    nome: str = Field(..., description="Nome do beneficiário final")

    model_config = ConfigDict(populate_by_name=True, extra='forbid', str_strip_whitespace=True)

class RateioCreditosItemModel(BaseModel):
    """Modelo Pydantic para item de rateio de créditos"""
    numeroBanco: int = Field(..., description="Número do banco")
    numeroAgencia: int = Field(..., description="Número da agência")
    numeroContaCorrente: int = Field(..., description="Número da conta corrente")
    valor: float = Field(..., description="Valor do rateio")

    model_config = ConfigDict(populate_by_name=True, extra='forbid', str_strip_whitespace=True)

class SicoobBoletoRequestPayload(BaseModel):
    """Modelo Pydantic principal para requisição de boleto Sicoob"""
    numeroCliente: int = Field(..., description="Número do cliente no Sicoob")
    codigoModalidade: int = Field(..., description="Código da modalidade de cobrança")
    numeroContaCorrente: int = Field(..., description="Número da conta corrente")
    codigoEspecieDocumento: str = Field(..., description="Código da espécie do documento")
    dataEmissao: str = Field(..., description="Data de emissão")
    nossoNumero: int = Field(..., description="Nosso número")
    seuNumero: str = Field(..., description="Seu número")
    identificacaoBoletoEmpresa: str = Field(..., description="Identificação do boleto na empresa")
    identificacaoEmissaoBoleto: int = Field(..., description="Identificação da emissão do boleto")
    identificacaoDistribuicaoBoleto: int = Field(..., description="Identificação da distribuição do boleto")
    valor: float = Field(..., gt=0, description="Valor do boleto")
    dataVencimento: str = Field(..., description="Data de vencimento")
    dataLimitePagamento: str = Field(..., description="Data limite para pagamento")
    valorAbatimento: float = Field(..., description="Valor do abatimento")
    tipoDesconto: int = Field(..., description="Tipo do desconto")
    dataPrimeiroDesconto: str = Field(..., description="Data do primeiro desconto")
    valorPrimeiroDesconto: float = Field(..., description="Valor do primeiro desconto")
    dataSegundoDesconto: Optional[str] = Field(None, description="Data do segundo desconto")
    valorSegundoDesconto: Optional[float] = Field(None, description="Valor do segundo desconto")
    dataTerceiroDesconto: Optional[str] = Field(None, description="Data do terceiro desconto")
    valorTerceiroDesconto: Optional[float] = Field(None, description="Valor do terceiro desconto")
    tipoMulta: int = Field(..., description="Tipo da multa")
    dataMulta: str = Field(..., description="Data da multa")
    valorMulta: float = Field(..., description="Valor da multa")
    tipoJurosMora: int = Field(..., description="Tipo dos juros de mora")
    dataJurosMora: str = Field(..., description="Data dos juros de mora")
    valorJurosMora: float = Field(..., description="Valor dos juros de mora")
    numeroParcela: int = Field(..., description="Número da parcela")
    aceite: bool = Field(..., description="Aceite do boleto")
    codigoNegativacao: Optional[int] = Field(None, description="Código de negativação")
    numeroDiasNegativacao: Optional[int] = Field(None, description="Número de dias para negativação")
    codigoProtesto: Optional[int] = Field(None, description="Código de protesto")
    numeroDiasProtesto: Optional[int] = Field(None, description="Número de dias para protesto")
    pagador: PagadorModel = Field(..., description="Dados do pagador")
    beneficiarioFinal: Optional[BeneficiarioFinalModel] = Field(None, description="Dados do beneficiário final")
    mensagensInstrucao: Optional[List[str]] = Field(None, description="Mensagens de instrução")
    gerarPdf: bool = Field(False, description="Gerar PDF do boleto")
    rateioCreditos: Optional[List[RateioCreditosItemModel]] = Field(None, description="Dados do rateio de créditos")
    codigoCadastrarPIX: Optional[int] = Field(None, description="Código para cadastrar PIX")
    numeroContratoCobranca: Optional[int] = Field(None, description="Número do contrato de cobrança")

    model_config = ConfigDict(populate_by_name=True, extra='forbid', str_strip_whitespace=True)

    @field_validator('dataEmissao', 'dataVencimento', 'dataLimitePagamento', 'dataPrimeiroDesconto', 'dataSegundoDesconto', 'dataTerceiroDesconto', 'dataMulta', 'dataJurosMora')
    def validate_date(cls, v):
        """Valida e formata as datas"""
        if isinstance(v, date):
            return v.isoformat()
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
            return True, modelo.model_dump(), ""
        except Exception as e:
            erros = []
            for error in e.errors():
                campo = " -> ".join(str(loc) for loc in error['loc'])
                msg = error['msg']
                
                # Mapeamento de mensagens de erro comuns
                if "field required" in msg:
                    msg = f"Campo obrigatório"
                elif "must be greater than" in msg:
                    msg = f"Deve ser maior que zero"
                elif "invalid date format" in msg:
                    msg = f"Formato de data inválido"
                elif "string does not match pattern" in msg:
                    if "CPF" in campo or "CNPJ" in campo:
                        msg = "CPF/CNPJ inválido"
                    elif "CEP" in campo:
                        msg = "CEP deve conter 8 dígitos"
                    elif "UF" in campo:
                        msg = "UF deve ser 2 letras maiúsculas"
                    elif "email" in campo:
                        msg = "E-mail inválido"
                
                erros.append(f"Campo '{campo}': {msg}")
            
            return False, {}, "\n".join(erros)

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